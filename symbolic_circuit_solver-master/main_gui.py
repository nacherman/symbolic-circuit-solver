import sys
import json
import pprint # Not used, but was in original
import subprocess
import tempfile
import os
import re
import glob
import sympy

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QTextEdit, QListWidget, QListWidgetItem, QDockWidget, QGraphicsView,
                             QGraphicsScene, QGraphicsItem, QFrame, QLabel, QFormLayout, QLineEdit,
                             QMenuBar, QAction, QFileDialog, QMessageBox, QTabWidget,
                             QTableWidget, QTableWidgetItem, QHeaderView,
                             QScrollArea, QInputDialog, QComboBox, QPushButton, QDialog,
                             QDialogButtonBox, QMenu)
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QDrag, QPolygonF, QFont, QPixmap, QPainterPath
from PyQt5.QtCore import Qt, QRectF, QPointF, QMimeData, QLineF

# SI Suffix to multiplier for parsing component values
SI_SUFFIX_TO_MULTIPLIER = {
    'f': 1e-15, 'p': 1e-12, 'n': 1e-9, 'u': 1e-6, 'm': 1e-3,
    'k': 1e3, 'K': 1e3, 'M': 1e6, 'Meg': 1e6, 'G': 1e9, 'T': 1e12
}

def parse_value_with_si_suffix(value_str):
    value_str = str(value_str).strip()
    if not value_str:
        return value_str # Return empty string if input is empty

    for suffix, multiplier in SI_SUFFIX_TO_MULTIPLIER.items():
        if value_str.endswith(suffix):
            try:
                numeric_part = float(value_str[:-len(suffix)])
                return numeric_part * multiplier
            except ValueError:
                return value_str # Invalid numeric part, return original string

    try: # If no suffix, try to convert to float directly
        return float(value_str)
    except ValueError:
        return value_str # Not a float, return original string (could be symbolic)

class BaseComponentItem(QGraphicsItem):
    item_counters = {} # Static dictionary to count items of each type for default naming
    TERMINAL_A = 0 # Standardized terminal ID
    TERMINAL_B = 1 # Standardized terminal ID for two-terminal components

    def __init__(self, name=None, value="1", default_prefix="X", num_terminals=2, parent=None):
        super().__init__(parent)
        component_type = self.COMPONENT_TYPE # Must be defined in subclasses

        if component_type not in BaseComponentItem.item_counters:
            BaseComponentItem.item_counters[component_type] = 0

        if name is None:
            BaseComponentItem.item_counters[component_type] += 1
            self._name = f"{default_prefix}{BaseComponentItem.item_counters[component_type]}"
        else:
            self._name = name

        self._value = value # Can be numeric (string) or symbolic (string)

        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges) # For wire updates

        self.font = QFont("Arial", 8)
        self.terminal_radius = 4
        self.snap_radius = 10 # For snapping wires to terminals
        self.width = 60 # Default component body width
        self.height = 30 # Default component body height
        self.lead_length = 20 # Default lead length

        self.local_terminals = {} # Dict: terminal_id -> QPointF (local coords)
        self.terminal_connections = {} # Dict: terminal_id -> list of WireItem connected
        for i in range(num_terminals):
            self.terminal_connections[i] = []

    @property
    def name(self):
        return self._name

    def set_name(self, new_name):
        new_name_stripped = str(new_name).strip().replace(" ", "_") # Basic sanitization
        if not new_name_stripped:
            # Try to get main window to show status message
            if hasattr(self.scene(), 'views') and self.scene().views():
                main_window = self.scene().views()[0].window()
                if hasattr(main_window, 'statusBar'):
                    main_window.statusBar().showMessage("Component name cannot be empty.", 3000)
            return # Do not set empty name
        if self._name != new_name_stripped:
            self.prepareGeometryChange()
            self._name = new_name_stripped
            self.update()

    @property
    def value(self):
        return self._value

    def set_value(self, new_value):
        new_value_str = str(new_value) # Ensure it's a string
        if self._value != new_value_str:
            self.prepareGeometryChange()
            self._value = new_value_str
            self.update()

    def common_paint_logic(self, painter, show_plus_minus=False):
        painter.setFont(self.font)
        text_y_offset = self.height / 2 + 5
        name_rect = QRectF(-self.width / 2, -text_y_offset - 10, self.width, 15)
        value_rect = QRectF(-self.width / 2, text_y_offset - 5, self.width, 15)

        painter.setPen(Qt.black)
        painter.drawText(name_rect, Qt.AlignCenter | Qt.AlignBottom, self.name)

        display_value_str = ""
        vs_item = self if isinstance(self, VoltageSourceItem) else None

        if self.COMPONENT_TYPE == GroundComponentItem.COMPONENT_TYPE:
            pass # Ground has no value to display
        elif vs_item: # Voltage source has special display
            display_value_str = f"AC:{vs_item.ac_magnitude}V {vs_item.ac_phase}deg (DC {vs_item.value}V)" if vs_item.source_type == "AC" else f"DC:{vs_item.value}V"
        else:
            display_value_str = self.value
        painter.drawText(value_rect, Qt.AlignCenter | Qt.AlignTop, display_value_str)

        # Draw terminals
        terminal_brush = QBrush(Qt.black)
        painter.setPen(QPen(Qt.black, 1))
        painter.setBrush(terminal_brush)
        for t_pos in self.local_terminals.values():
            painter.drawEllipse(t_pos, self.terminal_radius, self.terminal_radius)

        # Optional +/- for voltage sources
        if show_plus_minus and hasattr(self, 'TERMINAL_PLUS') and hasattr(self, 'TERMINAL_MINUS') and \
           self.TERMINAL_PLUS in self.local_terminals and self.TERMINAL_MINUS in self.local_terminals:
            plus_pos = self.local_terminals[self.TERMINAL_PLUS]
            minus_pos = self.local_terminals[self.TERMINAL_MINUS]
            painter.setPen(QPen(Qt.black, 1))
            font_metric = painter.fontMetrics()
            char_vertical_offset = font_metric.ascent() / 2
            painter.drawText(plus_pos + QPointF(self.terminal_radius + 2, char_vertical_offset), "+")
            painter.drawText(minus_pos + QPointF(self.terminal_radius + 2, char_vertical_offset), "-")

        if self.isSelected():
            pen = QPen(Qt.blue, 1, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.boundingRect().adjusted(-2, -2, 2, 2))

    def rotate_item(self, angle_degrees=90):
        self.setRotation(self.rotation() + angle_degrees)
        # ItemPositionHasChanged will trigger wire updates via itemChange

    def get_terminal_scene_positions(self):
        """Returns a dict: terminal_id -> QPointF (scene coordinates)"""
        return {tid: self.mapToScene(pos) for tid, pos in self.local_terminals.items()}

    def connect_wire(self, terminal_id, wire_item):
        if terminal_id in self.terminal_connections:
            if wire_item not in self.terminal_connections[terminal_id]:
                self.terminal_connections[terminal_id].append(wire_item)

    def disconnect_wire(self, terminal_id, wire_item):
        if terminal_id in self.terminal_connections and wire_item in self.terminal_connections[terminal_id]:
            self.terminal_connections[terminal_id].remove(wire_item)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged or change == QGraphicsItem.ItemRotationHasChanged:
            # Update connected wires when component moves or rotates
            if hasattr(self, 'terminal_connections'): # Ensure it's initialized
                for term_id_key in self.terminal_connections: # terminal_id is the key
                    for wire in self.terminal_connections[term_id_key]:
                        if hasattr(wire, 'update_endpoints_from_connections'):
                            wire.update_endpoints_from_connections()
        return super().itemChange(change, value)

class ResistorItem(BaseComponentItem):
    COMPONENT_TYPE = "R"
    def __init__(self, name=None, value="1k", parent=None):
        super().__init__(name, value, "R", 2, parent)
        # Define terminal positions in local coordinates
        self.local_terminals = {
            self.TERMINAL_A: QPointF(-self.width / 2 - self.lead_length, 0),
            self.TERMINAL_B: QPointF(self.width / 2 + self.lead_length, 0)
        }
    def boundingRect(self): # Generous bounding rect for text, leads, selection outline
        overall_width = self.width + 2 * self.lead_length + 2 * self.terminal_radius + 20 # Name/Value text
        overall_height = self.height + 2 * self.terminal_radius + 40 # Name/Value text
        max_dim = max(overall_width, overall_height) * 1.2 # Margin for rotation
        return QRectF(-max_dim/2, -max_dim/2, max_dim, max_dim)
    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        body_rect = QRectF(-self.width / 2, -self.height / 2, self.width, self.height)
        painter.setPen(QPen(Qt.black, 2))
        painter.setBrush(QBrush(Qt.white))
        painter.drawRect(body_rect) # Resistor body
        # Leads
        painter.setPen(QPen(Qt.black, 2))
        painter.drawLine(QPointF(-self.width / 2, 0), self.local_terminals[self.TERMINAL_A])
        painter.drawLine(QPointF(self.width / 2, 0), self.local_terminals[self.TERMINAL_B])
        self.common_paint_logic(painter)

class VoltageSourceItem(BaseComponentItem):
    COMPONENT_TYPE = "V"
    TERMINAL_PLUS = BaseComponentItem.TERMINAL_A # Alias for clarity
    TERMINAL_MINUS = BaseComponentItem.TERMINAL_B # Alias for clarity
    def __init__(self, name=None, value="1", source_type="DC", ac_magnitude="1", ac_phase="0", parent=None):
        super().__init__(name, value, "V", 2, parent)
        self.source_type = source_type # "DC" or "AC"
        self.ac_magnitude = ac_magnitude
        self.ac_phase = ac_phase
        self.radius = 20 # Radius of the circle
        self.width = self.radius * 2 # For common_paint_logic text placement
        self.height = self.radius * 2
        self.local_terminals = {
            self.TERMINAL_PLUS: QPointF(0, -self.radius - self.lead_length),
            self.TERMINAL_MINUS: QPointF(0, self.radius + self.lead_length)
        }
    def set_source_type(self, type_str): self.source_type = type_str; self.update()
    def set_ac_magnitude(self, mag_str): self.ac_magnitude = str(mag_str); self.update()
    def set_ac_phase(self, phase_str): self.ac_phase = str(phase_str); self.update()
    def get_spice_value_string(self): # Used in SPICE netlist generation
        if self.source_type == "AC":
            # For AC, SPICE format is often "AC <magnitude> <phase>" or just <dc_offset> AC <magnitude> <phase>
            # scs.py might expect just the magnitude for the simple "Vname n+ n- AC_MAG" and then .ac line.
            # Or, for transient AC: "SIN(offset amplitude frequency delay damping phase)"
            # For now, assume scs.py handles AC magnitude from here, and DC offset from 'value'.
            # If scs.py expects "AC <mag> <phase>" on the V line, this needs to change.
            # Based on current scs.py, it seems to take the primary value on the V line
            # and .ac specifies the sweep, not individual source AC properties beyond its magnitude.
            # Let's assume the 'value' is DC offset, and 'ac_magnitude' is for the .AC analysis part or if source is purely AC.
            # The provided bridge_circuit.sp used "V1 n1 0 1V" - simple DC value.
            # If we want "V1 n1 0 DC 0V AC 1V 0deg", scs.py parser needs to support that.
            # Current simple approach: if AC source type, its main "value" for SPICE line is its AC mag. DC offset is separate.
            # This means self.value is DC offset, self.ac_magnitude is AC amplitude.
            # The SPICE line for V might be `Vname n+ n- <DC_OFFSET_VALUE> AC <AC_MAG> <AC_PHASE>`
            # However, scs.py parser (scs_parser.py) seems to expect:
            # V<name> <n+> <n-> [value | SIN(...) | PULSE(...)] [AC <acmag> <acphase>]
            # So, we should provide the DC value (self.value) and then optionally "AC self.ac_magnitude self.ac_phase"
            # Let's refine this:
            base_val = self.value # This is the DC component
            if self.source_type == "AC":
                # Append AC specification if magnitude is non-zero or explicitly set.
                # Ensure ac_magnitude and ac_phase are valid numbers if specified.
                try: float(self.ac_magnitude); float(self.ac_phase)
                except ValueError: return base_val # Invalid AC params, return DC only
                return f"{base_val} AC {self.ac_magnitude} {self.ac_phase}"
            return base_val # Just DC value
        return self.value # Default to DC value
    def boundingRect(self):
        overall_dim = (self.radius + self.lead_length + self.terminal_radius + 20) * 2 # Generous
        return QRectF(-overall_dim/2, -overall_dim/2, overall_dim, overall_dim)
    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        circle_rect = QRectF(-self.radius, -self.radius, 2 * self.radius, 2 * self.radius)
        painter.setPen(QPen(Qt.black, 2))
        painter.setBrush(QBrush(Qt.white))
        painter.drawEllipse(circle_rect) # Source body
        if self.source_type == "AC": # Draw sine wave symbol
            path = QPainterPath()
            path.moveTo(-self.radius * 0.6, 0)
            path.quadTo(-self.radius * 0.3, -self.radius * 0.5, 0, 0) # Upper curve
            path.quadTo(self.radius * 0.3, self.radius * 0.5, self.radius * 0.6, 0)  # Lower curve
            painter.drawPath(path)
        # Leads
        painter.setPen(QPen(Qt.black, 2))
        painter.drawLine(QPointF(0, -self.radius), self.local_terminals[self.TERMINAL_PLUS])
        painter.drawLine(QPointF(0, self.radius), self.local_terminals[self.TERMINAL_MINUS])
        self.common_paint_logic(painter, show_plus_minus=True)

class CapacitorItem(BaseComponentItem):
    COMPONENT_TYPE = "C"
    def __init__(self, name=None, value="1u", parent=None):
        super().__init__(name, value, "C", 2, parent)
        self.plate_spacing = 6  # Distance between plates
        self.plate_length = self.height # Length of plates
        self.local_terminals = {
            self.TERMINAL_A: QPointF(-self.plate_spacing / 2 - self.lead_length, 0),
            self.TERMINAL_B: QPointF(self.plate_spacing / 2 + self.lead_length, 0)
        }
    def boundingRect(self):
        overall_width = self.plate_spacing + 2 * self.lead_length + 2 * self.terminal_radius + self.width + 20 # Text
        overall_height = self.plate_length + 2 * self.terminal_radius + 40 # Text
        max_dim = max(overall_width, overall_height) * 1.2
        return QRectF(-max_dim/2, -max_dim/2, max_dim, max_dim)
    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(Qt.black, 2))
        # Leads
        plate1_x = -self.plate_spacing / 2
        plate2_x = self.plate_spacing / 2
        painter.drawLine(self.local_terminals[self.TERMINAL_A], QPointF(plate1_x, 0))
        painter.drawLine(QPointF(plate1_x, -self.plate_length / 2), QPointF(plate1_x, self.plate_length / 2)) # Plate 1
        painter.drawLine(self.local_terminals[self.TERMINAL_B], QPointF(plate2_x, 0))
        painter.drawLine(QPointF(plate2_x, -self.plate_length / 2), QPointF(plate2_x, self.plate_length / 2)) # Plate 2
        self.common_paint_logic(painter)

class InductorItem(BaseComponentItem):
    COMPONENT_TYPE = "L"
    def __init__(self, name=None, value="1mH", parent=None):
        super().__init__(name, value, "L", 2, parent)
        self.num_loops = 3
        self.loop_radius = self.height / 2 # Use component height for loop radius
        self.local_terminals = {
            self.TERMINAL_A: QPointF(-self.width / 2 - self.lead_length, 0),
            self.TERMINAL_B: QPointF(self.width / 2 + self.lead_length, 0)
        }
    def boundingRect(self):
        overall_width = self.width + 2 * self.lead_length + 2 * self.terminal_radius + 20 # Text
        overall_height = self.height + 2 * self.terminal_radius + 40 # Text
        max_dim = max(overall_width, overall_height) * 1.2
        return QRectF(-max_dim/2, -max_dim/2, max_dim, max_dim)
    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(Qt.black, 2))
        # Lead A to first loop
        painter.drawLine(self.local_terminals[self.TERMINAL_A], QPointF(-self.width / 2, 0))
        # Inductor loops
        path = QPainterPath()
        path.moveTo(-self.width / 2, 0)
        loop_width = self.width / self.num_loops
        for i in range(self.num_loops):
            path.arcTo(-self.width / 2 + i * loop_width, -self.loop_radius, loop_width, 2 * self.loop_radius, 180.0, -180.0)
        painter.drawPath(path)
        # Last loop to Lead B
        painter.drawLine(QPointF(self.width / 2, 0), self.local_terminals[self.TERMINAL_B])
        self.common_paint_logic(painter)

class GroundComponentItem(BaseComponentItem):
    COMPONENT_TYPE = "GND"
    TERMINAL_CONNECTION = BaseComponentItem.TERMINAL_A # Only one terminal
    def __init__(self, name=None, parent=None): # Value is not used
        super().__init__(name, "", "GND", 1, parent) # default_prefix, num_terminals
        self.width = 30 # Visual width of the ground symbol
        self.height = 20 # Visual height of the ground symbol lines
        self.local_terminals = {
            self.TERMINAL_CONNECTION: QPointF(0, -self.height / 2) # Connection point at top
        }
    def boundingRect(self): # Bounding rect for the symbol itself
        return QRectF(-self.width / 2, -self.height / 2 - 5, self.width, self.height + 10) # Extra space for lead stub
    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(Qt.black, 2))
        # Vertical line (lead stub)
        p1 = self.local_terminals[self.TERMINAL_CONNECTION]
        p2 = QPointF(p1.x(), p1.y() + self.height) # Bottom of the vertical line
        painter.drawLine(p1, p2)
        # Horizontal lines
        line_len_coeff = 0.8
        for i in range(3): # Three horizontal lines
            current_line_width = self.width * line_len_coeff
            y_pos = p2.y() - i * (self.height / 3.5) # Lines get shorter towards top
            painter.drawLine(QPointF(p1.x() - current_line_width / 2, y_pos),
                             QPointF(p1.x() + current_line_width / 2, y_pos))
            line_len_coeff *= 0.7 # Reduce length for next line
        self.common_paint_logic(painter) # For name (if any) & selection

class WireItem(QGraphicsItem):
    COMPONENT_TYPE = "Wire" # For identification
    def __init__(self, start_connection=None, end_connection=None, parent=None):
        super().__init__(parent)
        self.start_conn = start_connection # Tuple: (BaseComponentItem, terminal_id) or None
        self.end_conn = end_connection   # Tuple: (BaseComponentItem, terminal_id) or None
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setZValue(-1) # Draw wires below components

        self.p1_scene = QPointF() # Start point in scene coordinates
        self.p2_scene = QPointF() # End point in scene coordinates
        self.update_endpoints_from_connections()

    def update_endpoints_from_connections(self):
        new_p1 = QPointF()
        new_p2 = QPointF()

        if self.start_conn:
            comp, term_id = self.start_conn
            if comp.scene() and hasattr(comp, 'local_terminals') and term_id in comp.local_terminals:
                new_p1 = comp.mapToScene(comp.local_terminals[term_id])

        if self.end_conn:
            comp, term_id = self.end_conn
            if comp.scene() and hasattr(comp, 'local_terminals') and term_id in comp.local_terminals:
                new_p2 = comp.mapToScene(comp.local_terminals[term_id])

        if self.p1_scene != new_p1 or self.p2_scene != new_p2:
            self.prepareGeometryChange()
            self.p1_scene = new_p1
            self.p2_scene = new_p2
            self.update()

    def get_scene_points(self):
        return self.p1_scene, self.p2_scene

    def boundingRect(self):
        if self.p1_scene.isNull() or self.p2_scene.isNull():
            return QRectF()
        # Create a rect from the wire's local coordinates
        return QRectF(self.mapFromScene(self.p1_scene), self.mapFromScene(self.p2_scene)).normalized().adjusted(-5, -5, 5, 5) # Margin for selection

    def paint(self, painter, option, widget=None):
        if self.p1_scene.isNull() or self.p2_scene.isNull():
            return

        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(Qt.darkCyan, 2)
        if self.isSelected():
            pen.setColor(Qt.blue)
            pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.drawLine(self.mapFromScene(self.p1_scene), self.mapFromScene(self.p2_scene))

    def cleanup_connections(self):
        """Disconnect this wire from its connected components."""
        if self.start_conn:
            comp, term_id = self.start_conn
            if hasattr(comp, 'disconnect_wire'): comp.disconnect_wire(term_id, self)
        if self.end_conn:
            comp, term_id = self.end_conn
            if hasattr(comp, 'disconnect_wire'): comp.disconnect_wire(term_id, self)
        self.start_conn = None
        self.end_conn = None

class SchematicView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setAcceptDrops(True)
        self.current_tool = None # e.g., "Wire"
        self.wire_start_connection = None # Stores (component_item, terminal_id) for wire drawing
        self.temp_line_item = None # Visual feedback for wire drawing
        self.snapped_connection_end = None # Potential end connection during wire drawing

    def set_tool(self, tool_name):
        self.current_tool = tool_name
        self.wire_start_connection = None # Reset wire drawing state
        self.snapped_connection_end = None
        if self.temp_line_item and self.temp_line_item.scene():
            self.scene().removeItem(self.temp_line_item)
        self.temp_line_item = None
        self.setCursor(Qt.CrossCursor if tool_name == "Wire" else Qt.ArrowCursor)

    def _get_snapped_connection(self, scene_pos):
        """Finds if scene_pos is close to any component terminal."""
        for item in self.scene().items():
            if isinstance(item, BaseComponentItem) and item.COMPONENT_TYPE != "Wire" and \
               hasattr(item, 'get_terminal_scene_positions') and hasattr(item, 'snap_radius'):
                for term_id, term_scene_pos in item.get_terminal_scene_positions().items():
                    if (term_scene_pos - scene_pos).manhattanLength() < item.snap_radius * 2: # Increased snap area
                        return item, term_id, term_scene_pos # Component, terminal ID, terminal scene pos
        return None

    def dropEvent(self, event):
        if event.mimeData().hasFormat("application/x-componentname"):
            component_name_bytes = event.mimeData().data("application/x-componentname")
            component_name = component_name_bytes.data().decode('utf-8')

            if component_name == "Wire": # Wires are not dropped, they are drawn
                event.ignore()
                return

            drop_pos = self.mapToScene(event.pos())
            item_instance = None
            if component_name == ResistorItem.COMPONENT_TYPE: item_instance = ResistorItem()
            elif component_name == VoltageSourceItem.COMPONENT_TYPE: item_instance = VoltageSourceItem()
            elif component_name == CapacitorItem.COMPONENT_TYPE: item_instance = CapacitorItem()
            elif component_name == InductorItem.COMPONENT_TYPE: item_instance = InductorItem()
            elif component_name == GroundComponentItem.COMPONENT_TYPE: item_instance = GroundComponentItem()

            if item_instance:
                item_instance.setPos(drop_pos)
                self.scene().addItem(item_instance)
                event.acceptProposedAction()
            else:
                event.ignore()
            self.set_tool(None) # Reset tool after drop
        else:
            super().dropEvent(event)

    def mousePressEvent(self, event):
        if self.current_tool == "Wire":
            scene_pos = self.mapToScene(event.pos())
            if event.button() == Qt.LeftButton:
                snapped_data = self._get_snapped_connection(scene_pos)
                if not self.wire_start_connection: # Start of wire
                    if snapped_data:
                        self.wire_start_connection = (snapped_data[0], snapped_data[1]) # comp, term_id
                        start_draw_pos = snapped_data[2] # term_scene_pos
                        # Create temporary line for visual feedback
                        self.temp_line_item = self.scene().addLine(
                            QLineF(start_draw_pos, start_draw_pos),
                            QPen(Qt.darkGray, 1, Qt.DashLine)
                        )
                else: # End of wire
                    end_conn_data = self.snapped_connection_end or (snapped_data if snapped_data else None)
                    if end_conn_data:
                        start_comp, start_term_id = self.wire_start_connection
                        end_comp, end_term_id = end_conn_data[0], end_conn_data[1]
                        # Avoid self-connection to same terminal or connecting two terminals of the same component (for 2-term comps)
                        if not (start_comp == end_comp and start_term_id == end_term_id):
                            # For 2-terminal components, also disallow connecting its own terminals together via a wire.
                            # This check might need adjustment for multi-terminal (>2) components if they are ever implemented.
                            is_same_comp_diff_term = (start_comp == end_comp and start_term_id != end_term_id and \
                                                    len(start_comp.local_terminals) <= 2 and len(end_comp.local_terminals) <=2)

                            if not is_same_comp_diff_term:
                                wire = WireItem(self.wire_start_connection, (end_comp, end_term_id))
                                self.scene().addItem(wire)
                                # Connect wire to components
                                if hasattr(start_comp, 'connect_wire'): start_comp.connect_wire(start_term_id, wire)
                                if hasattr(end_comp, 'connect_wire'): end_comp.connect_wire(end_term_id, wire)

                    # Reset wire drawing state
                    self.wire_start_connection = None
                    self.snapped_connection_end = None
                    if self.temp_line_item and self.temp_line_item.scene():
                        self.scene().removeItem(self.temp_line_item)
                    self.temp_line_item = None
            elif event.button() == Qt.RightButton: # Cancel wire drawing
                self.wire_start_connection = None
                self.snapped_connection_end = None
                if self.temp_line_item and self.temp_line_item.scene():
                    self.scene().removeItem(self.temp_line_item)
                self.temp_line_item = None
                self.set_tool(None) # Exit wire mode
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.current_tool == "Wire" and self.wire_start_connection and self.temp_line_item:
            scene_pos = self.mapToScene(event.pos())
            start_comp, start_term_id = self.wire_start_connection

            # Ensure start component and terminal are still valid (e.g., not deleted during draw)
            if not start_comp.scene() or not hasattr(start_comp, 'local_terminals') or start_term_id not in start_comp.local_terminals:
                self.wire_start_connection = None; self.snapped_connection_end = None
                if self.temp_line_item.scene(): self.scene().removeItem(self.temp_line_item)
                self.temp_line_item = None; self.set_tool(None)
                return

            start_draw_pos = start_comp.mapToScene(start_comp.local_terminals[start_term_id])

            snapped_data = self._get_snapped_connection(scene_pos)
            if snapped_data:
                self.snapped_connection_end = (snapped_data[0], snapped_data[1]) # comp, term_id
                end_draw_pos = snapped_data[2] # term_scene_pos
                self.temp_line_item.setPen(QPen(Qt.green, 2, Qt.DashLine)) # Snap color
            else:
                self.snapped_connection_end = None
                end_draw_pos = scene_pos # Free-floating end point
                self.temp_line_item.setPen(QPen(Qt.darkGray, 1, Qt.DashLine)) # Default color
            self.temp_line_item.setLine(QLineF(start_draw_pos, end_draw_pos))
        else:
            super().mouseMoveEvent(event)

    def contextMenuEvent(self, event):
        item = self.itemAt(event.pos())
        if isinstance(item, BaseComponentItem) and item.COMPONENT_TYPE != "Wire": # Context menu for components
            menu = QMenu(self)
            rotate_action = menu.addAction("Rotate")
            delete_action = menu.addAction("Delete")
            action = menu.exec_(event.globalPos())
            if action == rotate_action and hasattr(item, 'rotate_item'):
                item.rotate_item(90)
            elif action == delete_action:
                self._delete_item_and_connections(item)
        elif isinstance(item, WireItem): # Context menu for wires
            menu = QMenu(self)
            delete_action = menu.addAction("Delete Wire")
            action = menu.exec_(event.globalPos())
            if action == delete_action:
                self._delete_item_and_connections(item)
        else:
            super().contextMenuEvent(event)

    def _delete_item_and_connections(self, item_to_delete):
        if not item_to_delete or not item_to_delete.scene(): return

        if isinstance(item_to_delete, WireItem):
            item_to_delete.cleanup_connections() # Disconnect from components
        elif isinstance(item_to_delete, BaseComponentItem): # Component deletion
            # Iterate over a copy of lists as they might be modified during cleanup
            for term_id_key in list(item_to_delete.terminal_connections.keys()):
                for wire in list(item_to_delete.terminal_connections[term_id_key]):
                    wire.cleanup_connections() # Disconnect wire from both ends
                    if wire.scene(): self.scene().removeItem(wire) # Remove wire from scene

        self.scene().removeItem(item_to_delete) # Remove the item itself

    def keyPressEvent(self, event):
        selected_items = self.scene().selectedItems()
        if event.key() == Qt.Key_R:
            if selected_items:
                for item in selected_items:
                    if hasattr(item, 'rotate_item'): item.rotate_item(90)
            else: super().keyPressEvent(event)
        elif event.key() == Qt.Key_Delete or event.key() == Qt.Key_Backspace:
            if selected_items:
                # Delete a copy of the list, as deleting modifies the selection
                for item in list(selected_items): self._delete_item_and_connections(item)
            else: super().keyPressEvent(event)
        elif event.key() == Qt.Key_Escape:
            if self.current_tool == "Wire": # Cancel wire drawing
                self.wire_start_connection = None
                self.snapped_connection_end = None
                if self.temp_line_item and self.temp_line_item.scene():
                    self.scene().removeItem(self.temp_line_item)
                self.temp_line_item = None
            self.set_tool(None) # Exit any active tool mode
        else:
            super().keyPressEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-componentname"):
            component_name = event.mimeData().data("application/x-componentname").data().decode('utf-8')
            if component_name and component_name != "Wire":
                self.set_tool(None) # Ensure not in wire mode if dragging component
                event.acceptProposedAction()
            else: # "Wire" cannot be dragged
                event.ignore()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event): # Generally accept moves if dragEnterEvent accepted
        if event.mimeData().hasFormat("application/x-componentname"):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

class ComponentListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True) # Allow dragging from this list
        # Populate with available component types
        self.addItems([
            ResistorItem.COMPONENT_TYPE, VoltageSourceItem.COMPONENT_TYPE,
            CapacitorItem.COMPONENT_TYPE, InductorItem.COMPONENT_TYPE,
            GroundComponentItem.COMPONENT_TYPE, "Wire" # "Wire" is a special tool, not a draggable item
        ])
        self.itemClicked.connect(self.on_item_clicked)
        self.parent_view = None # Will be set by SchematicEditor

    def on_item_clicked(self, item):
        if self.parent_view and item.text() == "Wire":
            self.parent_view.set_tool("Wire")
        # Other items are handled by drag-and-drop

    def startDrag(self, supportedActions):
        item = self.currentItem()
        if item and item.text() != "Wire": # "Wire" is not dragged
            mime_data = QMimeData()
            # Use a custom MIME type for component name
            mime_data.setData("application/x-componentname", item.text().encode('utf-8'))

            drag = QDrag(self)
            drag.setMimeData(mime_data)
            # Optional: set a pixmap for the drag cursor
            # drag.setPixmap(QPixmap("path/to/icon.png"))
            drag.exec_(supportedActions)
        # else: do nothing for "Wire" or no item selected

class PropertiesWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QFormLayout(self)
        self.current_item = None

        self.name_edit = QLineEdit()
        self.layout.addRow("Name:", self.name_edit)

        self.value_label = QLabel("Value (DC):") # Label changes for VSource
        self.value_edit = QLineEdit()
        self.layout.addRow(self.value_label, self.value_edit)

        # Voltage Source Specific Fields (initially hidden)
        self.source_type_combo = QComboBox()
        self.source_type_combo.addItems(["DC", "AC"])
        self.ac_mag_edit = QLineEdit()
        self.ac_phase_edit = QLineEdit("0") # Default phase

        # Store widgets to easily show/hide them
        self.vs_specific_widgets = []

        # AddRow returns the label and field widgets, but QFormLayout doesn't directly give access to the row itself.
        # So, we get the widgets associated with the row to control visibility.
        label_st = QLabel("Source Type:")
        self.layout.addRow(label_st, self.source_type_combo)
        self.vs_specific_widgets.extend([label_st, self.source_type_combo])

        label_ac_mag = QLabel("AC Magnitude:")
        self.layout.addRow(label_ac_mag, self.ac_mag_edit)
        self.vs_specific_widgets.extend([label_ac_mag, self.ac_mag_edit])

        label_ac_phase = QLabel("AC Phase (deg):")
        self.layout.addRow(label_ac_phase, self.ac_phase_edit)
        self.vs_specific_widgets.extend([label_ac_phase, self.ac_phase_edit])


        # Connections
        self.name_edit.editingFinished.connect(self.on_name_changed)
        self.value_edit.editingFinished.connect(self.on_value_changed)
        self.source_type_combo.currentIndexChanged.connect(self.on_source_type_changed)
        self.ac_mag_edit.editingFinished.connect(self.on_ac_mag_changed)
        self.ac_phase_edit.editingFinished.connect(self.on_ac_phase_changed)

        self.clear_properties() # Initial state

    def set_vs_specific_widgets_visible(self, visible):
        for widget in self.vs_specific_widgets:
            widget.setVisible(visible)

    def display_properties(self, item):
        self.current_item = item
        is_voltage_source = isinstance(item, VoltageSourceItem)
        is_ground = (hasattr(item, 'COMPONENT_TYPE') and item.COMPONENT_TYPE == GroundComponentItem.COMPONENT_TYPE)

        self.set_vs_specific_widgets_visible(is_voltage_source)

        if isinstance(item, BaseComponentItem) and item.COMPONENT_TYPE != "Wire":
            self.name_edit.setText(item.name)
            self.name_edit.setEnabled(True)

            self.value_label.setText("DC Value/Offset:" if is_voltage_source else "Value:")
            if is_ground:
                self.value_edit.setText("") # Ground has no value
                self.value_edit.setEnabled(False)
            else:
                self.value_edit.setText(item.value)
                self.value_edit.setEnabled(True)

            if is_voltage_source:
                self.source_type_combo.setCurrentIndex(self.source_type_combo.findText(item.source_type))
                self.ac_mag_edit.setText(item.ac_magnitude)
                self.ac_phase_edit.setText(item.ac_phase)
                # Visibility of AC mag/phase fields depends on type being AC
                self.on_source_type_changed() # Call to ensure AC fields visibility is correct based on current type
        else:
            self.clear_properties()

    def clear_properties(self):
        self.current_item = None
        self.name_edit.setText("")
        self.value_edit.setText("")
        self.name_edit.setEnabled(False)
        self.value_edit.setEnabled(False)
        self.value_label.setText("Value:")

        self.set_vs_specific_widgets_visible(False)
        self.source_type_combo.setCurrentIndex(0) # Default to DC
        self.ac_mag_edit.setText("")
        self.ac_phase_edit.setText("0")


    def on_name_changed(self):
        if self.current_item and hasattr(self.current_item, 'set_name'):
            new_name = self.name_edit.text().strip().replace(" ", "_")
            if not new_name:
                QMessageBox.warning(self, "Invalid Name", "Component name cannot be empty.")
                self.name_edit.setText(self.current_item.name) # Revert to old name
                return
            self.current_item.set_name(new_name)

    def _validate_and_set_numeric_value(self, line_edit, item_setter_method_name, original_value_attr_name, allow_symbolic=True, is_phase_value=False):
        if not self.current_item or not hasattr(self.current_item, item_setter_method_name):
            return

        new_text_value = line_edit.text().strip()
        # Get original value directly from attribute for reversion, not from another widget
        original_display_value = str(getattr(self.current_item, original_value_attr_name))


        parsed_value = parse_value_with_si_suffix(new_text_value)

        if isinstance(parsed_value, (float, int)):
            value_to_set = new_text_value if is_phase_value else str(parsed_value)
            getattr(self.current_item, item_setter_method_name)(value_to_set)
        elif allow_symbolic and not is_phase_value and isinstance(parsed_value, str):
            if re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", parsed_value):
                getattr(self.current_item, item_setter_method_name)(parsed_value)
            else:
                QMessageBox.warning(self, "Invalid Input", f"Symbolic value '{new_text_value}' contains invalid characters.")
                line_edit.setText(original_display_value)
        elif is_phase_value and isinstance(parsed_value, str):
             try:
                 float(parsed_value)
                 getattr(self.current_item, item_setter_method_name)(parsed_value)
             except ValueError:
                 QMessageBox.warning(self, "Invalid Input", f"Phase value '{new_text_value}' is not a valid number.")
                 line_edit.setText(original_display_value)
        else:
            QMessageBox.warning(self, "Invalid Input", f"Value '{new_text_value}' is not a valid numeric value.")
            line_edit.setText(original_display_value)


    def on_value_changed(self):
        if self.current_item and hasattr(self.current_item, 'set_value') and \
           not (hasattr(self.current_item, 'COMPONENT_TYPE') and self.current_item.COMPONENT_TYPE == GroundComponentItem.COMPONENT_TYPE):
            # Pass the name of the attribute that holds the original value string
            self._validate_and_set_numeric_value(self.value_edit, "set_value", "value")


    def on_source_type_changed(self, index=None):
        if self.current_item and isinstance(self.current_item, VoltageSourceItem):
            source_type = self.source_type_combo.currentText()
            self.current_item.set_source_type(source_type)
            is_ac = (source_type == "AC")

            # Show/hide AC specific fields based on new source_type
            # Iterate through the specifically stored AC widgets for visibility control
            for widget in self.vs_specific_widgets:
                if widget in [self.ac_mag_edit, self.ac_phase_edit] or \
                   (isinstance(widget, QLabel) and (widget.text() == "AC Magnitude:" or widget.text() == "AC Phase (deg):")):
                    widget.setVisible(is_ac)

            self.value_label.setText("DC Value/Offset:" if is_ac else "DC Value:")


    def on_ac_mag_changed(self):
        if self.current_item and isinstance(self.current_item, VoltageSourceItem):
            self._validate_and_set_numeric_value(self.ac_mag_edit, "set_ac_magnitude", "ac_magnitude")

    def on_ac_phase_changed(self):
        if self.current_item and isinstance(self.current_item, VoltageSourceItem):
            self._validate_and_set_numeric_value(self.ac_phase_edit, "set_ac_phase", "ac_phase", allow_symbolic=False, is_phase_value=True)

class ACAnalysisDialog(QDialog):
    def __init__(self, parent=None, current_params=None):
        super().__init__(parent)
        self.setWindowTitle("AC Analysis Parameters")
        layout = QFormLayout(self)

        self.sweep_type_combo = QComboBox()
        self.sweep_type_combo.addItems(["DEC", "LIN", "OCT"]) # Standard SPICE AC sweep types
        layout.addRow("Sweep Type:", self.sweep_type_combo)

        self.points_edit = QLineEdit("10") # Number of points
        layout.addRow("Number of Points:", self.points_edit)

        self.fstart_edit = QLineEdit("1")   # Start frequency
        layout.addRow("Start Frequency (Hz):", self.fstart_edit)

        self.fstop_edit = QLineEdit("1M") # Stop frequency
        layout.addRow("Stop Frequency (Hz):", self.fstop_edit)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        if current_params: self.populate_params(current_params)

    def populate_params(self, params):
        self.sweep_type_combo.setCurrentText(params.get('type', 'DEC'))
        self.points_edit.setText(params.get('points', '10'))
        self.fstart_edit.setText(params.get('fstart', '1'))
        self.fstop_edit.setText(params.get('fstop', '1M'))

    def get_params(self):
        # Basic validation could be added here if desired (e.g., ensure points is int)
        return {
            'type': self.sweep_type_combo.currentText(),
            'points': self.points_edit.text(),
            'fstart': self.fstart_edit.text(),
            'fstop': self.fstop_edit.text()
        }

class SchematicEditor(QMainWindow):
    FAVORITES_DIR = "circuits/favorites" # Class constant for favorites directory

    def __init__(self):
        super().__init__()
        self.current_filename = None # For Save/Save As
        self.temp_files_to_cleanup = [] # Store paths of temp files for deletion on close
        self.ac_analysis_params = None # Stores dict from ACAnalysisDialog
        self.parsed_measure_results = {} # Stores parsed v(node) results from simulation

        # Ensure favorites directory exists
        os.makedirs(self.FAVORITES_DIR, exist_ok=True)

        self.initUI()

    def initUI(self):
        self.setWindowTitle('Symbolic Circuit Schematic Editor')
        self.setGeometry(100, 100, 1600, 900) # x, y, width, height

        # --- Central Widget: Schematic View ---
        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(-400, -300, 800, 600) # Define scene boundaries
        self.scene.selectionChanged.connect(self.on_scene_selection_changed)
        self.schematic_view = SchematicView(self.scene, self)
        self.schematic_view.setFrameShape(QFrame.StyledPanel) # Add a border
        self.schematic_view.setRenderHint(QPainter.Antialiasing) # Smooth rendering
        self.setCentralWidget(self.schematic_view)

        # --- Dock Widget: Component List ---
        components_dock = QDockWidget("Components", self)
        self.component_list_widget = ComponentListWidget()
        self.component_list_widget.parent_view = self.schematic_view # Link for tool selection
        components_dock.setWidget(self.component_list_widget)
        self.addDockWidget(Qt.LeftDockWidgetArea, components_dock)

        # --- Dock Widget: Properties Editor ---
        properties_dock = QDockWidget("Properties", self)
        self.properties_widget = PropertiesWidget()
        properties_dock.setWidget(self.properties_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, properties_dock)
        self.properties_widget.clear_properties() # Start with empty fields

        # --- Dock Widget: Output and Formulas (Tabbed) ---
        self.output_tabs = QTabWidget() # Made it an attribute for easier access
        self.solver_log_output_area = QTextEdit()
        self.solver_log_output_area.setReadOnly(True)
        self.solver_log_output_area.setFont(QFont("Monospace", 9))
        self.output_tabs.addTab(self.solver_log_output_area, "Solver Log & Raw Output")

        self.measured_results_table = QTableWidget()
        self.measured_results_table.setColumnCount(3)
        self.measured_results_table.setHorizontalHeaderLabels(["Measurement Name", "Expression", "Result Value"])
        self.measured_results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.measured_results_table.setEditTriggers(QTableWidget.NoEditTriggers) # Read-only
        self.output_tabs.addTab(self.measured_results_table, "Measured Results")

        self.plots_tab_widget_container = QWidget() # Container for scroll area
        self.plots_layout = QVBoxLayout(self.plots_tab_widget_container)
        self.plots_scroll_area = QScrollArea()
        self.plots_scroll_area.setWidgetResizable(True)
        self.plots_scroll_area.setWidget(self.plots_tab_widget_container)
        self.output_tabs.addTab(self.plots_scroll_area, "Plots")

        self.solution_path_area = QTextEdit()
        self.solution_path_area.setReadOnly(True)
        self.solution_path_area.setFont(QFont("Monospace", 9))
        self.output_tabs.addTab(self.solution_path_area, "Solution Path / Analysis Steps")

        output_dock = QDockWidget("Output", self)
        output_dock.setWidget(self.output_tabs)
        self.addDockWidget(Qt.BottomDockWidgetArea, output_dock)

        # --- Menu Bar ---
        menubar = self.menuBar()
        file_menu = menubar.addMenu('&File')

        open_action = QAction('&Open Circuit...', self); open_action.setShortcut('Ctrl+O'); open_action.setToolTip("Open a circuit from a JSON file"); open_action.triggered.connect(self.open_circuit); file_menu.addAction(open_action)
        save_action = QAction('&Save Circuit', self); save_action.setShortcut('Ctrl+S'); save_action.setToolTip("Save the current circuit"); save_action.triggered.connect(self.save_circuit); file_menu.addAction(save_action)
        save_as_action = QAction('Save Circuit &As...', self); save_as_action.setShortcut('Ctrl+Shift+S'); save_as_action.setToolTip("Save the current circuit to a new file"); save_as_action.triggered.connect(self.save_circuit_as); file_menu.addAction(save_as_action)
        file_menu.addSeparator()
        add_favorite_action = QAction('Add to &Favorites...', self); add_favorite_action.setToolTip("Save current circuit to favorites"); add_favorite_action.triggered.connect(self.add_to_favorites); file_menu.addAction(add_favorite_action)
        open_favorite_action = QAction('Open &Favorite...', self); open_favorite_action.setToolTip("Open a circuit from favorites"); open_favorite_action.triggered.connect(self.open_favorite); file_menu.addAction(open_favorite_action)
        file_menu.addSeparator()
        exit_action = QAction('&Exit', self); exit_action.setShortcut('Ctrl+Q'); exit_action.setToolTip("Exit the application"); exit_action.triggered.connect(self.close); file_menu.addAction(exit_action) # Changed to self.close

        circuit_menu = menubar.addMenu('&Circuit')
        run_sim_action = QAction('&Run Simulation', self); run_sim_action.setToolTip("Generate netlist and run simulation"); run_sim_action.triggered.connect(self.run_simulation); circuit_menu.addAction(run_sim_action)
        set_ac_action = QAction('Set &AC Analysis...', self); set_ac_action.setToolTip("Configure AC analysis parameters"); set_ac_action.triggered.connect(self.set_ac_analysis_dialog); circuit_menu.addAction(set_ac_action)

        self.statusBar().showMessage('Ready.')

        # Auto-load and run test circuit for sandbox verification
        test_circuit_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_circuits", "voltage_divider_symbolic.json")
        if os.path.exists(test_circuit_path):
            print(f"Attempting to auto-load test circuit: {test_circuit_path}")
            self.open_circuit_from_file(test_circuit_path)
            print("Test circuit loaded, attempting to run simulation...")
            self.run_simulation()
            print("Simulation run (if any components were loaded). Check output areas.")
            # Print results to stdout for sandbox verification
            print("\n--- Solver Log & Raw Output (from main_gui.py) ---")
            print(self.solver_log_output_area.toPlainText())
            print("\n--- Solution Path & Analysis (from main_gui.py) ---")
            print(self.solution_path_area.toPlainText())
            print("\n--- Parsed Measure Results (from main_gui.py) ---")
            # import json # for pretty printing dict # Already imported globally
            print(json.dumps(self.parsed_measure_results, indent=2))
            print("\n--- End of Auto-Run Output ---")
        else:
            print(f"Test circuit file not found: {test_circuit_path}")

    # This auto-run logic will be moved to main()
    # def _perform_auto_test_run(self):
    #     test_circuit_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_circuits", "voltage_divider_symbolic.json")
    #     if os.path.exists(test_circuit_path):
    #         print(f"Attempting to auto-load test circuit: {test_circuit_path}")
    #         self.open_circuit_from_file(test_circuit_path)
    #         print("Test circuit loaded, attempting to run simulation...")
    #         self.run_simulation()
    #         print("Simulation run (if any components were loaded). Check output areas.")
    #         # Print results to stdout for sandbox verification
    #         print("\n--- Solver Log & Raw Output (from main_gui.py) ---")
    #         print(self.solver_log_output_area.toPlainText())
    #         print("\n--- Solution Path & Analysis (from main_gui.py) ---")
    #         print(self.solution_path_area.toPlainText())
    #         print("\n--- Parsed Measure Results (from main_gui.py) ---")
    #         # import json # for pretty printing dict # Already imported globally
    #         print(json.dumps(self.parsed_measure_results, indent=2))
    #         print("\n--- End of Auto-Run Output ---")
    #     else:
    #         print(f"Test circuit file not found: {test_circuit_path}")


    def set_ac_analysis_dialog(self):
        dialog = ACAnalysisDialog(self, self.ac_analysis_params)
        if dialog.exec_() == QDialog.Accepted:
            self.ac_analysis_params = dialog.get_params()
            self.statusBar().showMessage(f"AC analysis parameters set: {self.ac_analysis_params['type']} "
                                         f"{self.ac_analysis_params['points']} points, "
                                         f"{self.ac_analysis_params['fstart']} to {self.ac_analysis_params['fstop']} Hz.", 3000)
        else:
            self.statusBar().showMessage("AC analysis setup cancelled.", 2000)

    def _clear_plots_tab(self):
        # Clear previous plots
        while self.plots_layout.count():
            child = self.plots_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def _parse_and_display_measure_results(self, results_content_str):
        self.measured_results_table.setRowCount(0)
        self.parsed_measure_results.clear()

        pattern = re.compile(
            r"^(?P<name>\S+?):\s*"
            r"(?P<expr>v\([\w\.\-\+]+\)|i\([\w\.\-\+]+\)|isub\([\w\.\-\+]+\)|[\w\.\-\+]+)\s*"
            r"=\s*---------------------\s*"
            r"(?P<value>.+?)"
            r"(?=(?:\r?\n){2}\S+?:|\Z)",
            re.MULTILINE | re.DOTALL
        )

        matches_found = 0
        for match in pattern.finditer(results_content_str):
            matches_found += 1
            data = match.groupdict()
            name_str = data['name'].strip()
            expr_str = data['expr'].strip()
            value_str = data['value'].strip().replace("\n", " ")

            row_position = self.measured_results_table.rowCount()
            self.measured_results_table.insertRow(row_position)
            self.measured_results_table.setItem(row_position, 0, QTableWidgetItem(name_str))
            self.measured_results_table.setItem(row_position, 1, QTableWidgetItem(expr_str))
            self.measured_results_table.setItem(row_position, 2, QTableWidgetItem(value_str))

            if expr_str.startswith("v(") and expr_str.endswith(")"):
                self.parsed_measure_results[expr_str] = value_str # Corrected: Use dict item assignment

        if matches_found == 0:
            self.measured_results_table.insertRow(0)
            self.measured_results_table.setItem(0, 0, QTableWidgetItem("No .measure results found in the output."))
            self.measured_results_table.setSpan(0, 0, 1, 3)

    def _generate_spice_netlist_string(self, netlist_component_data, all_unique_node_names_for_spice):
        spice_lines = ["* Auto-generated SPICE netlist from GUI"]

        components_added_to_netlist = False
        for comp_data in netlist_component_data:
            if comp_data['type'] != GroundComponentItem.COMPONENT_TYPE:
                # Node list should already be correctly ordered (e.g. V+, V- for VoltageSource)
                nodes_str = " ".join(comp_data['nodes'])
                spice_lines.append(f"{comp_data['name']} {nodes_str} {comp_data['value']}")
                components_added_to_netlist = True

        if not components_added_to_netlist and not any(c['type'] == GroundComponentItem.COMPONENT_TYPE for c in netlist_component_data):
             spice_lines.append("* Empty circuit: No components defined.")
        elif not components_added_to_netlist and any(c['type'] == GroundComponentItem.COMPONENT_TYPE for c in netlist_component_data):
             spice_lines.append("* Circuit contains only ground symbol(s). Node 0 is defined.")


        for node_name in sorted(list(all_unique_node_names_for_spice)):
            # if node_name != "0": # Option: Do not measure v(0)
            sanitized_node_name = re.sub(r'[^a-zA-Z0-9_]', '_', node_name) # Make name SPICE-friendly
            spice_lines.append(f".measure dc gui_v_{sanitized_node_name} v({node_name})") # Added 'dc' for clarity if it's DC analysis

        if self.ac_analysis_params:
            ac = self.ac_analysis_params
            # Validate AC parameters before adding to netlist
            try:
                float(ac['points']); float(parse_value_with_si_suffix(ac['fstart'])); float(parse_value_with_si_suffix(ac['fstop']))
                spice_lines.append(f".ac {ac['type']} {ac['points']} {ac['fstart']} {ac['fstop']}")
                # Add measure for AC node voltages if desired, e.g. .measure ac vm(node)
                for node_name in sorted(list(all_unique_node_names_for_spice)):
                    sanitized_node_name = re.sub(r'[^a-zA-Z0-9_]', '_', node_name)
                    spice_lines.append(f".measure ac gui_vac_{sanitized_node_name} v({node_name})")

            except ValueError:
                 self.solver_log_output_area.append("Warning: Invalid AC parameters. .ac line not added.")


        spice_lines.append(".end")
        return "\n".join(spice_lines)

    def run_simulation(self):
        self.solver_log_output_area.clear()
        self.measured_results_table.setRowCount(0)
        self._clear_plots_tab()
        self.solution_path_area.clear()
        self.parsed_measure_results.clear()

        all_items = self.scene.items()
        components = [item for item in all_items if isinstance(item, BaseComponentItem) and item.COMPONENT_TYPE != "Wire"]
        wires = [item for item in all_items if isinstance(item, WireItem)]

        if not components:
            self.solver_log_output_area.setText("No components in the schematic to simulate.")
            return

        # DSU Implementation
        dsu_parent = {}
        def dsu_find(item_terminal_tuple):
            # Ensure item_terminal_tuple is hashable and properly formed
            if not isinstance(item_terminal_tuple, tuple) or len(item_terminal_tuple) != 2:
                # This case should ideally not happen if inputs are correct
                # print(f"Warning: Invalid item_terminal_tuple for DSU find: {item_terminal_tuple}")
                return item_terminal_tuple # Or handle error appropriately

            if item_terminal_tuple not in dsu_parent:
                dsu_parent[item_terminal_tuple] = item_terminal_tuple

            # Path compression
            path = []
            current = item_terminal_tuple
            while dsu_parent[current] != current:
                path.append(current)
                current = dsu_parent[current]
            for node_in_path in path:
                dsu_parent[node_in_path] = current
            return current


        def dsu_union(tuple1, tuple2):
            root1 = dsu_find(tuple1)
            root2 = dsu_find(tuple2)
            if root1 != root2:
                dsu_parent[root2] = root1

        all_component_terminals_init = []
        ground_terminal_representatives = set()

        for comp in components:
            if hasattr(comp, 'local_terminals'):
                for term_id in comp.local_terminals.keys():
                    terminal_tuple = (comp, term_id)
                    all_component_terminals_init.append(terminal_tuple)
                    # Initialize each terminal in DSU by finding it
                    dsu_find(terminal_tuple)
                    if comp.COMPONENT_TYPE == GroundComponentItem.COMPONENT_TYPE:
                        ground_terminal_representatives.add(dsu_find(terminal_tuple))

        for wire in wires:
            if wire.start_conn and wire.end_conn:
                # Ensure wire terminals are also initialized in DSU before union
                dsu_find(wire.start_conn)
                dsu_find(wire.end_conn)
                dsu_union(wire.start_conn, wire.end_conn)

        if len(ground_terminal_representatives) > 1:
            # All ground symbols must belong to the same electrical net ("0").
            # Merge their DSU sets.
            first_ground_rep = list(ground_terminal_representatives)[0]
            for other_ground_rep in list(ground_terminal_representatives)[1:]:
                dsu_union(first_ground_rep, other_ground_rep)
            # Update the set to contain only the single, unified representative for ground.
            if first_ground_rep : # check if not None
                 ground_terminal_representatives = {dsu_find(first_ground_rep)}


        node_rep_to_name_map = {}
        next_node_number = 1

        # Determine the final DSU representative for the ground node, if any ground exists.
        # This rep will be assigned name "0".
        unified_dsu_ground_rep = None
        if ground_terminal_representatives: # Check if the set is not empty
            # Get the single representative for ground (all ground terminals should now be in the same set)
            # Call dsu_find on one of its members to ensure we get the ultimate root.
            unified_dsu_ground_rep = dsu_find(list(ground_terminal_representatives)[0])


        # Get all unique DSU representatives (roots of sets)
        # Sort for somewhat deterministic node naming (n1, n2, etc.)
        # The key tries to ensure ground ("0") is processed first if it exists.
        all_unique_reps = sorted(
            list(set(dsu_find(ct_tuple) for ct_tuple in all_component_terminals_init)),
            key=lambda rep: (rep != unified_dsu_ground_rep, id(rep[0]), rep[1]) # Prioritize ground rep
        )

        for rep in all_unique_reps:
            if rep not in node_rep_to_name_map: # If this representative hasn't been named yet
                if unified_dsu_ground_rep and rep == unified_dsu_ground_rep:
                    node_rep_to_name_map[rep] = "0"
                # If no ground symbol exists, the first representative encountered (due to sort) becomes "0"
                elif not unified_dsu_ground_rep and "0" not in node_rep_to_name_map.values():
                    node_rep_to_name_map[rep] = "0"
                else:
                    node_rep_to_name_map[rep] = f"n{next_node_number}"
                    next_node_number += 1

        all_unique_node_names_for_spice = set(node_rep_to_name_map.values())
        final_node_names_for_all_comps = {}
        netlist_component_data = []

        for comp in components:
            if hasattr(comp, 'local_terminals') and comp.COMPONENT_TYPE != "Wire":
                comp_node_list_for_spice = []
                # For components like V, L, C, R, order of terminals matters for SPICE.
                # Usually TERMINAL_A (positive/first) then TERMINAL_B (negative/second).
                # GroundComponentItem has only TERMINAL_CONNECTION (aliased to TERMINAL_A).

                # Define a canonical order for terminals for consistent SPICE output
                # For VoltageSource, ensure TERMINAL_PLUS comes before TERMINAL_MINUS
                if isinstance(comp, VoltageSourceItem):
                    terminal_ids_ordered = [VoltageSourceItem.TERMINAL_PLUS, VoltageSourceItem.TERMINAL_MINUS]
                else: # For R, C, L, Ground - default sorted order is usually fine (0 then 1)
                    terminal_ids_ordered = sorted(list(comp.local_terminals.keys()))

                for term_id in terminal_ids_ordered:
                    if term_id not in comp.local_terminals: continue # Should not happen with correct setup

                    representative = dsu_find((comp, term_id))
                    node_name = node_rep_to_name_map.get(representative, f"unmapped_node_{comp.name}_t{term_id}")
                    comp_node_list_for_spice.append(node_name)
                    final_node_names_for_all_comps[(comp, term_id)] = node_name

                if comp.COMPONENT_TYPE != GroundComponentItem.COMPONENT_TYPE:
                    netlist_component_data.append({
                        'type': comp.COMPONENT_TYPE,
                        'name': comp.name,
                        'nodes': comp_node_list_for_spice, # Already ordered
                        'value': comp.get_spice_value_string() if hasattr(comp, 'get_spice_value_string') else comp.value
                    })

        spice_netlist_str = self._generate_spice_netlist_string(netlist_component_data, all_unique_node_names_for_spice)
        self.solution_path_area.append("Generated SPICE Netlist:\n" + spice_netlist_str)
        self.solver_log_output_area.append("SPICE Netlist:\n" + spice_netlist_str + "\n" + "-"*20 + "\n")

        temp_spice_filepath = None
        temp_results_base_filepath_stem = None
        temp_dir = tempfile.gettempdir()

        try:
            fd, temp_spice_filepath = tempfile.mkstemp(suffix='.sp', prefix='gui_sim_', text=True, dir=temp_dir)
            with os.fdopen(fd, 'w') as tmp_sp_file:
                tmp_sp_file.write(spice_netlist_str)
            self.temp_files_to_cleanup.append(temp_spice_filepath)

            temp_results_base_filepath_stem = os.path.join(temp_dir, os.path.splitext(os.path.basename(temp_spice_filepath))[0])

            script_dir = os.path.dirname(os.path.abspath(__file__))
            scs_script_path = os.path.join(script_dir, "scs.py")

            command = ["python", scs_script_path, "-i", temp_spice_filepath, "-o", temp_results_base_filepath_stem]

            self.solver_log_output_area.append(f"Executing command: {' '.join(command)}\nWorking Directory: {script_dir}\n")

            process = subprocess.run(command, capture_output=True, text=True, cwd=script_dir, timeout=30)

            self.solver_log_output_area.append("Solver Standard Output:\n" + (process.stdout or "N/A"))
            self.solver_log_output_area.append("\nSolver Standard Error:\n" + (process.stderr or "N/A"))

            results_filepath = temp_results_base_filepath_stem + ".results"
            log_filepath = temp_results_base_filepath_stem + ".log"
            self.temp_files_to_cleanup.extend([results_filepath, log_filepath])

            if process.returncode == 0:
                self.statusBar().showMessage("Simulation completed successfully.", 5000)
                if os.path.exists(results_filepath):
                    with open(results_filepath, 'r') as f_results:
                        results_content = f_results.read()
                    self.solver_log_output_area.append("\n" + "-"*10 + "Raw Results" + "-"*10 + "\n" + results_content)
                    self._parse_and_display_measure_results(results_content)

                    self.solution_path_area.append("\n\n" + "-"*10 + "Component Symbolic Analysis (using measured node voltages)" + "-"*10 + "\n")
                    s_sym = sympy.symbols('s')

                    for comp_item in components: # Changed 'comp' to 'comp_item' to avoid conflict
                        if comp_item.COMPONENT_TYPE == GroundComponentItem.COMPONENT_TYPE: continue

                        comp_text_prefix = f"{comp_item.COMPONENT_TYPE} {comp_item.name} (Value: {comp_item.value}): "
                        analysis_text = ""
                        try:
                            if isinstance(comp_item, ResistorItem):
                                node1_name = final_node_names_for_all_comps.get((comp_item, ResistorItem.TERMINAL_A))
                                node2_name = final_node_names_for_all_comps.get((comp_item, ResistorItem.TERMINAL_B))
                                if node1_name and node2_name:
                                    v1_str = self.parsed_measure_results.get(f"v({node1_name})")
                                    v2_str = self.parsed_measure_results.get(f"v({node2_name})")
                                    if v1_str and v2_str:
                                        v1_expr = sympy.sympify(v1_str)
                                        v2_expr = sympy.sympify(v2_str)
                                        voltage_drop_expr = sympy.simplify(v1_expr - v2_expr)

                                        raw_r_val_str = comp_item.value
                                        parsed_numeric_r_val = parse_value_with_si_suffix(raw_r_val_str)
                                        r_expr_sym = sympy.sympify(parsed_numeric_r_val) if isinstance(parsed_numeric_r_val, (int, float)) else sympy.symbols(raw_r_val_str)

                                        current_expr_sym = sympy.simplify(voltage_drop_expr / r_expr_sym)
                                        analysis_text = f"V_drop = {voltage_drop_expr}, I_current = {current_expr_sym}"
                                    else: analysis_text = f"Missing voltage for node(s) {node1_name if not v1_str else ''} {node2_name if not v2_str else ''} in .measure results."
                                else: analysis_text = "Node name mapping error for resistor terminals."

                            elif isinstance(comp_item, CapacitorItem):
                                raw_c_val_str = comp_item.value
                                parsed_numeric_c_val = parse_value_with_si_suffix(raw_c_val_str)
                                if isinstance(parsed_numeric_c_val, (int,float)) and self.ac_analysis_params:
                                    c_expr_sym = sympy.sympify(parsed_numeric_c_val)
                                    zc_expr_sym = sympy.simplify(1 / (s_sym * c_expr_sym))
                                    analysis_text = f"Symbolic Impedance (Zc) = {zc_expr_sym}"
                                else: analysis_text = "(DC behavior: Open circuit. AC impedance if AC analysis run & numeric value.)"

                            elif isinstance(comp_item, InductorItem):
                                raw_l_val_str = comp_item.value
                                parsed_numeric_l_val = parse_value_with_si_suffix(raw_l_val_str)
                                if isinstance(parsed_numeric_l_val, (int,float)) and self.ac_analysis_params:
                                    l_expr_sym = sympy.sympify(parsed_numeric_l_val)
                                    zl_expr_sym = sympy.simplify(s_sym * l_expr_sym)
                                    analysis_text = f"Symbolic Impedance (Zl) = {zl_expr_sym}"
                                else: analysis_text = "(DC behavior: Short circuit. AC impedance if AC analysis run & numeric value.)"

                            elif isinstance(comp_item, VoltageSourceItem):
                                analysis_text = f"(Voltage/Current defined by source parameters or via .measure v(node)/i(source) results)"

                            self.solution_path_area.append(comp_text_prefix + analysis_text)
                        except Exception as e_sym_an:
                            self.solution_path_area.append(f"{comp_text_prefix} Error during symbolic analysis: {e_sym_an}")

                else:
                    self.solver_log_output_area.append(f"\nERROR: Results file '{results_filepath}' not found.")

                plot_files = glob.glob(temp_results_base_filepath_stem + "_*.png")
                self._clear_plots_tab()
                if plot_files:
                    for plot_file_path in sorted(plot_files):
                        pixmap = QPixmap(plot_file_path)
                        if not pixmap.isNull():
                            plot_label = QLabel()
                            plot_label.setPixmap(pixmap.scaledToWidth(self.plots_scroll_area.width() - 30, Qt.SmoothTransformation))
                            self.plots_layout.addWidget(plot_label)
                            self.temp_files_to_cleanup.append(plot_file_path)
                        else:
                            no_load_label = QLabel(f"Could not load plot: {os.path.basename(plot_file_path)}")
                            self.plots_layout.addWidget(no_load_label)
                    # Switch to plots tab if plots were generated and action was from menu
                    sender_action = self.sender()
                    if isinstance(sender_action, QAction) and sender_action.text() == "&Run Simulation":
                         if self.output_tabs: self.output_tabs.setCurrentWidget(self.plots_scroll_area)
                else:
                    no_plots_label = QLabel("No plots were generated by the simulation.")
                    self.plots_layout.addWidget(no_plots_label)

            else:
                self.statusBar().showMessage(f"Simulation failed (return code: {process.returncode}). Check log.", 5000)
                if os.path.exists(log_filepath):
                    with open(log_filepath, 'r') as f_log:
                        self.solver_log_output_area.append("\n" + "-"*10 + "Solver Log (on error)" + "-"*10 + "\n" + f_log.read())
                else:
                     self.solver_log_output_area.append(f"\nERROR: Log file '{log_filepath}' not found, but simulation failed.")


        except FileNotFoundError as e_fnf:
             QMessageBox.critical(self, "Simulation Error", f"scs.py not found. Ensure it's in the same directory as the GUI or in PATH.\nDetails: {e_fnf}")
             self.solver_log_output_area.append(f"\nPYTHON SCRIPT ERROR: scs.py not found. {e_fnf}")
        except subprocess.TimeoutExpired:
            QMessageBox.warning(self, "Simulation Timeout", "The simulation process timed out (30 seconds).")
            self.solver_log_output_area.append("\nSIMULATION TIMEOUT: Process took too long to complete.")
        except Exception as e:
            QMessageBox.critical(self, "Simulation Error", f"An unexpected error occurred during simulation: {type(e).__name__}: {e}")
            self.solver_log_output_area.append(f"\nPYTHON SCRIPT ERROR: {type(e).__name__}: {e}")


    def on_scene_selection_changed(self):
        selected = self.scene.selectedItems()
        if len(selected) == 1 and isinstance(selected[0], BaseComponentItem) and selected[0].COMPONENT_TYPE != "Wire":
            self.properties_widget.display_properties(selected[0])
        else:
            self.properties_widget.clear_properties()

    def save_circuit_as(self):
        default_path = self.current_filename or os.path.join(os.getcwd(), "untitled_circuit.json")
        filename, _ = QFileDialog.getSaveFileName(self, "Save Circuit As", default_path, "JSON Files (*.json);;All Files (*)")
        if filename:
            self.current_filename = filename
            self.save_circuit_to_file(filename)
            self.setWindowTitle(f"Schematic Editor - {os.path.basename(filename)}")
        else:
            self.statusBar().showMessage("Save As cancelled.", 2000)

    def save_circuit(self):
        if self.current_filename:
            self.save_circuit_to_file(self.current_filename)
        else:
            self.save_circuit_as()

    def save_circuit_to_file(self, filename):
        if not filename: return

        data_to_save = {'components': [], 'wires': []}
        # name_to_item_map = {} # Not strictly needed if we save by name directly

        for item in self.scene.items():
            if isinstance(item, BaseComponentItem) and item.COMPONENT_TYPE != "Wire":
                # name_to_item_map[item.name] = item
                comp_data = {
                    'type': item.COMPONENT_TYPE,
                    'name': item.name,
                    'value': (item.value if item.COMPONENT_TYPE != GroundComponentItem.COMPONENT_TYPE else ""),
                    'pos_x': item.pos().x(),
                    'pos_y': item.pos().y(),
                    'rotation': item.rotation()
                }
                if isinstance(item, VoltageSourceItem):
                    comp_data['source_type'] = item.source_type
                    comp_data['ac_magnitude'] = item.ac_magnitude
                    comp_data['ac_phase'] = item.ac_phase
                data_to_save['components'].append(comp_data)

        for item in self.scene.items():
            if isinstance(item, WireItem):
                start_comp_name = item.start_conn[0].name if item.start_conn and hasattr(item.start_conn[0], 'name') else None
                start_term_id = item.start_conn[1] if item.start_conn else None
                end_comp_name = item.end_conn[0].name if item.end_conn and hasattr(item.end_conn[0], 'name') else None
                end_term_id = item.end_conn[1] if item.end_conn else None

                if start_comp_name and end_comp_name and start_term_id is not None and end_term_id is not None:
                    wire_data = {
                        'type': WireItem.COMPONENT_TYPE, # "Wire"
                        'start_comp_name': start_comp_name,
                        'start_term_id': start_term_id,
                        'end_comp_name': end_comp_name,
                        'end_term_id': end_term_id
                    }
                    data_to_save['wires'].append(wire_data)
        try:
            with open(filename, 'w') as f:
                json.dump(data_to_save, f, indent=4)
            # No separate QMessageBox if called from add_to_favorites, handle it there.
            if not (self.sender() and hasattr(self.sender(), 'text') and self.sender().text() == 'Add to &Favorites...'): # Check attribute existence
                 QMessageBox.information(self, "Circuit Saved", f"Circuit successfully saved to:\n{filename}")
            self.statusBar().showMessage(f"Circuit saved to {filename}", 3000)
        except IOError as e:
            QMessageBox.warning(self, "Save Error", f"Could not save circuit to file: {e}")
            self.statusBar().showMessage(f"Error saving circuit: {e}", 3000)

    def open_circuit(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Open Circuit", os.getcwd(), "JSON Files (*.json);;All Files (*)")
        if filename:
            self.open_circuit_from_file(filename)
        else:
            self.statusBar().showMessage("Open circuit cancelled.", 2000)

    def open_circuit_from_file(self, filename):
        if not filename: return
        try:
            with open(filename, 'r') as f:
                circuit_data = json.load(f)
        except Exception as e:
            QMessageBox.critical(self, "Error Opening Circuit", f"Could not open or parse circuit file: {e}")
            return

        self.scene.clear()
        self.properties_widget.clear_properties()
        BaseComponentItem.item_counters.clear()
        self._cleanup_temp_files()
        self.ac_analysis_params = None
        self.parsed_measure_results.clear()

        item_by_name_map = {}

        for comp_dict in circuit_data.get('components', []): # Use 'components' key
            comp_type = comp_dict.get('type')
            name = comp_dict.get('name')
            value = comp_dict.get('value', "")
            pos_x = comp_dict.get('pos_x', 0)
            pos_y = comp_dict.get('pos_y', 0)
            rotation = comp_dict.get('rotation', 0)

            item_instance = None
            if comp_type == ResistorItem.COMPONENT_TYPE: item_instance = ResistorItem(name, value)
            elif comp_type == VoltageSourceItem.COMPONENT_TYPE:
                item_instance = VoltageSourceItem(name, value,
                                                  comp_dict.get('source_type', "DC"),
                                                  comp_dict.get('ac_magnitude', "1"),
                                                  comp_dict.get('ac_phase', "0"))
            elif comp_type == CapacitorItem.COMPONENT_TYPE: item_instance = CapacitorItem(name, value)
            elif comp_type == InductorItem.COMPONENT_TYPE: item_instance = InductorItem(name, value)
            elif comp_type == GroundComponentItem.COMPONENT_TYPE: item_instance = GroundComponentItem(name)

            if item_instance:
                item_instance.setPos(QPointF(pos_x, pos_y))
                item_instance.setRotation(rotation)
                self.scene.addItem(item_instance)
                item_by_name_map[name] = item_instance

        for wire_dict in circuit_data.get('wires', []): # Use 'wires' key
            start_comp_name = wire_dict.get('start_comp_name')
            start_term_id = wire_dict.get('start_term_id')
            end_comp_name = wire_dict.get('end_comp_name')
            end_term_id = wire_dict.get('end_term_id')

            start_comp = item_by_name_map.get(start_comp_name)
            end_comp = item_by_name_map.get(end_comp_name)

            if start_comp and end_comp and start_term_id is not None and end_term_id is not None:
                valid_start_term = hasattr(start_comp, 'local_terminals') and start_term_id in start_comp.local_terminals
                valid_end_term = hasattr(end_comp, 'local_terminals') and end_term_id in end_comp.local_terminals

                if valid_start_term and valid_end_term:
                    start_connection = (start_comp, start_term_id)
                    end_connection = (end_comp, end_term_id)
                    wire = WireItem(start_connection, end_connection)
                    self.scene.addItem(wire)
                    if hasattr(start_comp, 'connect_wire'): start_comp.connect_wire(start_term_id, wire)
                    if hasattr(end_comp, 'connect_wire'): end_comp.connect_wire(end_term_id, wire)
                else:
                    print(f"Warning: Invalid terminal ID for wire connection from file: {wire_dict}")

        if os.path.dirname(os.path.abspath(filename)) == os.path.abspath(self.FAVORITES_DIR):
            self.current_filename = None
            self.setWindowTitle(f"Schematic Editor - {os.path.basename(filename)} (from Favorites)")
        else:
            self.current_filename = filename
            self.setWindowTitle(f"Schematic Editor - {os.path.basename(filename)}")

        self.statusBar().showMessage(f"Loaded circuit: {os.path.basename(filename)}", 5000)

    def add_to_favorites(self):
        suggested_name = os.path.splitext(os.path.basename(self.current_filename))[0] if self.current_filename else ""

        fav_name, ok = QInputDialog.getText(self, "Add to Favorites",
                                            "Enter a name for this favorite circuit:",
                                            QLineEdit.Normal, suggested_name)
        if ok and fav_name:
            safe_fav_name = "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in fav_name).strip().replace(" ", "_")
            if not safe_fav_name: safe_fav_name = "unnamed_favorite"

            favorite_filepath = os.path.join(self.FAVORITES_DIR, safe_fav_name + ".json")

            if os.path.exists(favorite_filepath):
                reply = QMessageBox.question(self, "Confirm Overwrite",
                                             f"Favorite '{safe_fav_name}' already exists. Overwrite?",
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.No:
                    self.statusBar().showMessage("Add to favorites cancelled.", 2000)
                    return

            self.save_circuit_to_file(favorite_filepath)
            QMessageBox.information(self, "Favorite Saved", f"Circuit '{safe_fav_name}' saved to favorites.") # Show confirmation
        else:
            self.statusBar().showMessage("Add to favorites cancelled.", 2000)

    def open_favorite(self):
        if not os.path.exists(self.FAVORITES_DIR) or not os.listdir(self.FAVORITES_DIR):
            QMessageBox.information(self, "No Favorites", "No favorite circuits found to open.")
            return

        favorite_files = [f for f in os.listdir(self.FAVORITES_DIR) if f.endswith(".json")]
        if not favorite_files:
            QMessageBox.information(self, "No Favorites", "No JSON circuit files found in favorites directory.")
            return

        favorite_names = [os.path.splitext(f)[0] for f in favorite_files]

        chosen_fav_name, ok = QInputDialog.getItem(self, "Open Favorite Circuit",
                                                   "Select a favorite circuit to open:",
                                                   favorite_names, 0, False)
        if ok and chosen_fav_name:
            filepath_to_open = os.path.join(self.FAVORITES_DIR, chosen_fav_name + ".json")
            self.open_circuit_from_file(filepath_to_open)
        else:
            self.statusBar().showMessage("Open favorite cancelled.", 2000)

    def closeEvent(self, event):
        self._cleanup_temp_files()
        # event might be bool if called from self.close() via QAction, or QCloseEvent
        if isinstance(event, QCloseEvent): # Check if it's the actual QCloseEvent
            super().closeEvent(event) # Propagate to allow normal window closing procedure
        # else: if it's from self.close() triggered by QAction, no super().closeEvent() here
        # as self.close() itself handles it.

    def _cleanup_temp_files(self):
        cleaned_count = 0
        # Iterate over a copy for safe removal from the list
        for filepath in list(self.temp_files_to_cleanup):
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
                    cleaned_count +=1
                # Always try to remove from list, even if file was already deleted or never existed
                if filepath in self.temp_files_to_cleanup: # Check again before removal
                    self.temp_files_to_cleanup.remove(filepath)
            except OSError as e:
                # Log to console, not GUI, as this is usually on exit
                print(f"Warning: Could not delete temporary file {filepath}: {e}")
        if cleaned_count > 0:
             print(f"Cleaned up {cleaned_count} temporary simulation files.")


def main():
    # Use a simple relative path for the diagnostic output file
    diag_output_filename = "diagnostic_output.txt"
    print(f"Diagnostic output will be written to: {os.path.abspath(diag_output_filename)}") # Print absolute path for clarity

def main():
    diag_output_filename = "diagnostic_output.txt"
    is_headless_test = os.environ.get("RUN_HEADLESS_TEST") == "true"

    # Initialize app and editor to None; they will be created if not in full headless mode
    app = None
    editor = None

    print(f"Diagnostic output will be written to: {os.path.abspath(diag_output_filename)}")
    if is_headless_test:
        print("RUN_HEADLESS_TEST is true. Attempting to run without full GUI initialization.")

    try:
        with open(diag_output_filename, "w") as diag_file:
            diag_file.write(f"Starting diagnostic run... Headless test: {is_headless_test}\n")
            diag_file.flush()

            if not is_headless_test:
                diag_file.write("Attempting to instantiate QApplication...\n")
                diag_file.flush()
                app = QApplication(sys.argv)
                diag_file.write("QApplication instantiated.\n")
                diag_file.flush()

            # For SchematicEditor, its __init__ might still need QApplication even if not shown.
            # This is an exploratory step. If this still fails for headless,
            # SchematicEditor's logic needs more significant decoupling from QMainWindow.
            diag_file.write("Attempting to instantiate SchematicEditor...\n")
            diag_file.flush()
            # If app is None (headless), SchematicEditor might fail if it expects QApplication.instance()
            # or if its base class QMainWindow's __init__ requires it.
            # For now, we pass `app` which could be None. Some Qt widgets allow this for data models.
            # This is a temporary hack to see if we can even get to run_simulation.
            # Proper solution is to decouple simulation logic from QMainWindow.
            if not is_headless_test or QApplication.instance() is not None : # Ensure QApplication exists if editor needs it.
                 editor = SchematicEditor() # This will likely fail if app is None and QMainWindow needs it.
                 diag_file.write("SchematicEditor instantiated.\n")
                 diag_file.flush()
            else: # Headless mode and no QApplication instance.
                 # This path requires that SchematicEditor or a replacement can be used without QApplication.
                 # For now, we'll assume 'editor' stays None and try to call a static/class method if possible,
                 # or skip the parts that need 'editor' instance if it's None.
                 # This part of the logic is TBD based on SchematicEditor's structure.
                 # For this iteration, we'll let it be None and see.
                 diag_file.write("SchematicEditor NOT instantiated in this headless path as QApplication is also None.\n")
                 diag_file.flush()


            if editor: # Only proceed if editor was instantiated
                test_circuit_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_circuits", "voltage_divider_symbolic.json")
                diag_file.write(f"Looking for test circuit at: {test_circuit_path}\n")
                diag_file.flush()

                if os.path.exists(test_circuit_path):
                    diag_file.write(f"Attempting to auto-load test circuit: {test_circuit_path}\n")
                    diag_file.flush()
                    editor.open_circuit_from_file(test_circuit_path)
                    diag_file.write("Test circuit loaded, attempting to run simulation...\n")
                    diag_file.flush()
                    editor.run_simulation()
                    diag_file.write("Simulation run (if any components were loaded). Check output areas.\n")
                    diag_file.flush()

                    diag_file.write("\n--- Solver Log & Raw Output (from main_gui.py) ---\n")
                    diag_file.write(editor.solver_log_output_area.toPlainText() + "\n")
                    diag_file.write("\n--- Solution Path & Analysis (from main_gui.py) ---\n")
                    diag_file.write(editor.solution_path_area.toPlainText() + "\n")
                    diag_file.write("\n--- Parsed Measure Results (from main_gui.py) ---\n")
                    diag_file.write(json.dumps(editor.parsed_measure_results, indent=2) + "\n")
                    diag_file.write("\n--- End of Auto-Run Output ---\n")
                    diag_file.flush()
                else:
                    diag_file.write(f"Test circuit file not found: {test_circuit_path}\n")
                    diag_file.flush()
            else:
                diag_file.write("Editor not instantiated, skipping simulation run.\n")
                diag_file.flush()

            if is_headless_test:
                diag_file.write("RUN_HEADLESS_TEST is true. Clean exit path for headless mode.\n")
                diag_file.flush()
                # sys.exit(0) # This will be done outside the 'with open'
            else:
                diag_file.write("Diagnostic logging complete. Attempting to show GUI for normal run...\n")
                diag_file.flush()

    except Exception as e:
        try:
            # Use append mode for exceptions, in case file was partially written
            with open(diag_output_filename, "a") as diag_file_exc:
                diag_file_exc.write(f"\n!!! EXCEPTION DURING DIAGNOSTIC SETUP/RUN: {type(e).__name__}: {e} !!!\n")
                import traceback
                traceback.print_exc(file=diag_file_exc)
                diag_file_exc.flush()
        except Exception as e_nested:
            # Fallback to stdout if logging exception to file also fails
            print(f"Nested exception while writing main exception to diag file: {type(e_nested).__name__}: {e_nested}")
        print(f"EXCEPTION DURING DIAGNOSTIC SETUP/RUN: {type(e).__name__}: {e}")


    if is_headless_test:
        print("RUN_HEADLESS_TEST is true. Exiting cleanly after diagnostic file write.")
        sys.exit(0)

    if app and editor: # Check if app & editor were successfully initialized for GUI mode
        editor.show()
        sys.exit(app.exec_())
    else:
        # Ensure diag_file is closed if an exception happened before its normal close
        # This is tricky because diag_file is in 'try' scope.
        # For simplicity, assume it's closed or OS will handle it on script exit.
        print("QApplication or SchematicEditor not initialized for GUI mode (possibly due to an error, or headless mode logic path). Exiting.")
        sys.exit(1)


# --- Headless Simulation Logic ---
class HeadlessComponent:
    def __init__(self, comp_type, name, value, source_type=None, ac_magnitude=None, ac_phase=None):
        self.COMPONENT_TYPE = comp_type
        self.name = name
        self.value = value
        self.source_type = source_type
        self.ac_magnitude = ac_magnitude
        self.ac_phase = ac_phase
        # Simplified terminal representation for DSU: using (self, terminal_id)
        # For headless, terminal_id will just be 0 or 1 (or 0 for ground)
        self.local_terminals = {}
        if comp_type == "GND":
            self.local_terminals[BaseComponentItem.TERMINAL_A] = "conn_point" # Placeholder
        elif comp_type in ["R", "V", "C", "L"]:
            self.local_terminals[BaseComponentItem.TERMINAL_A] = "term_A"
            self.local_terminals[BaseComponentItem.TERMINAL_B] = "term_B"
            if comp_type == "V":
                 # Ensure consistent terminal naming for VoltageSource
                 self.TERMINAL_PLUS = BaseComponentItem.TERMINAL_A
                 self.TERMINAL_MINUS = BaseComponentItem.TERMINAL_B


    def get_spice_value_string(self): # Adapted from VoltageSourceItem
        if self.COMPONENT_TYPE == "V":
            base_val = self.value
            if self.source_type == "AC":
                try: float(self.ac_magnitude); float(self.ac_phase)
                except ValueError: return base_val
                return f"{base_val} AC {self.ac_magnitude} {self.ac_phase}"
            return base_val
        return self.value


class HeadlessWire:
    def __init__(self, start_comp_name, start_term_id, end_comp_name, end_term_id):
        self.start_comp_name = start_comp_name
        self.start_term_id = start_term_id
        self.end_comp_name = end_comp_name
        self.end_term_id = end_term_id
        # Resolved connections will be (HeadlessComponent_instance, terminal_id)
        self.start_conn = None
        self.end_conn = None


class HeadlessSimulator:
    def __init__(self):
        self.components = [] # List of HeadlessComponent
        self.wires = []      # List of HeadlessWire
        self.item_by_name_map = {} # For resolving wire connections by component name
        BaseComponentItem.item_counters.clear() # Reset counters for consistent naming if needed

        self.ac_analysis_params = None # Will be set if needed
        self.parsed_measure_results = {}
        self.temp_files_to_cleanup = [] # Manage temp files like in SchematicEditor

        self.solver_log_output = ""
        self.solution_path_output = ""


    def load_circuit_data(self, filepath):
        try:
            with open(filepath, 'r') as f:
                circuit_data = json.load(f)
        except Exception as e:
            self.solver_log_output += f"Error opening/parsing circuit file: {e}\n"
            print(f"Error opening/parsing circuit file: {e}")
            return False

        self.components.clear()
        self.wires.clear()
        self.item_by_name_map.clear()
        BaseComponentItem.item_counters.clear()

        for comp_dict in circuit_data.get('components', []):
            comp_type = comp_dict.get('type')
            name = comp_dict.get('name')
            value = comp_dict.get('value', "")

            hc = None
            if comp_type == VoltageSourceItem.COMPONENT_TYPE:
                hc = HeadlessComponent(comp_type, name, value,
                                       comp_dict.get('source_type', "DC"),
                                       comp_dict.get('ac_magnitude', "1"),
                                       comp_dict.get('ac_phase', "0"))
            elif comp_type in [ResistorItem.COMPONENT_TYPE, CapacitorItem.COMPONENT_TYPE, InductorItem.COMPONENT_TYPE, GroundComponentItem.COMPONENT_TYPE]:
                hc = HeadlessComponent(comp_type, name, value)

            if hc:
                self.components.append(hc)
                self.item_by_name_map[name] = hc
            else:
                self.solver_log_output += f"Unknown component type in JSON: {comp_type}\n"


        for wire_dict in circuit_data.get('wires', []):
            start_comp_name = wire_dict.get('start_comp_name')
            start_term_id = wire_dict.get('start_term_id')
            end_comp_name = wire_dict.get('end_comp_name')
            end_term_id = wire_dict.get('end_term_id')

            start_comp = self.item_by_name_map.get(start_comp_name)
            end_comp = self.item_by_name_map.get(end_comp_name)

            if start_comp and end_comp and start_term_id is not None and end_term_id is not None:
                # Basic validation (more can be added if terminal IDs are complex)
                valid_start_term = start_term_id in start_comp.local_terminals
                valid_end_term = end_term_id in end_comp.local_terminals

                if valid_start_term and valid_end_term:
                    hw = HeadlessWire(start_comp_name, start_term_id, end_comp_name, end_term_id)
                    hw.start_conn = (start_comp, start_term_id) # Store actual component instance and term_id
                    hw.end_conn = (end_comp, end_term_id)
                    self.wires.append(hw)
                else:
                    self.solver_log_output += f"Invalid terminal ID for wire from JSON: {wire_dict}\n"
            else:
                self.solver_log_output += f"Could not find components for wire from JSON: {wire_dict}\n"

        self.solver_log_output += f"Headless loaded {len(self.components)} components and {len(self.wires)} wires.\n"
        return True

    def run_simulation(self):
        # This method will be a complex adaptation of SchematicEditor.run_simulation
        # For now, just a placeholder
        self.solution_path_output += "HeadlessSimulator.run_simulation() called.\n"

        # --- TODO: Adapt DSU, node naming, SPICE gen, subprocess call, result parsing, SymPy analysis ---
        # Key data needed by the original run_simulation:
        # - self.components (list of HeadlessComponent)
        # - self.wires (list of HeadlessWire, with start_conn/end_conn resolved)
        # - self.ac_analysis_params (if any)
        # - self.parsed_measure_results (dict to be filled)
        # - self.solver_log_output (string to append to)
        # - self.solution_path_output (string to append to)
        # - self.temp_files_to_cleanup (list for managing temp files)

        # Placeholder for where SPICE netlist would be generated and run
        if not self.components:
            self.solver_log_output += "No components loaded for headless simulation.\n"
            return

        self.solver_log_output += "--- Headless Simulation Placeholder ---\n"
        self.solution_path_output += "DSU, SPICE gen, scs.py call, and SymPy analysis would happen here.\n"
        self.parsed_measure_results["v(n_placeholder)"] = "R_load * Isymbolic" # Example
        self.solution_path_output += "R R_placeholder (R_load): V_drop = 5*R_load/(1000+R_load), I_current = 5/(1000+R_load)\n" # Example

        # Need to adapt _generate_spice_netlist_string and _parse_and_display_measure_results
        # and the core DSU/node naming logic.
        # The subprocess call to scs.py remains the same.
        # Symbolic analysis part also needs adaptation to use HeadlessComponent attributes.

        # --- Start of DSU and Node Naming adaptation ---
        self.dsu_parent = {} # DSU parent map specific to this simulation run

        all_component_terminals_init = []
        ground_terminal_representatives = set()

        for comp in self.components:
            # Assuming HeadlessComponent has local_terminals dict like BaseComponentItem
            for term_id in comp.local_terminals.keys():
                terminal_tuple = (comp, term_id) # Using (HeadlessComponent instance, term_id)
                all_component_terminals_init.append(terminal_tuple)
                self._dsu_find(terminal_tuple) # Initialize in DSU
                if comp.COMPONENT_TYPE == "GND": # Using string type
                    ground_terminal_representatives.add(self._dsu_find(terminal_tuple))

        for wire in self.wires:
            # Wires should have start_conn and end_conn resolved during load_circuit_data
            # to be (HeadlessComponent instance, term_id)
            if wire.start_conn and wire.end_conn:
                self._dsu_find(wire.start_conn) # Ensure initialized
                self._dsu_find(wire.end_conn)   # Ensure initialized
                self._dsu_union(wire.start_conn, wire.end_conn)

        if len(ground_terminal_representatives) > 1:
            first_ground_rep = list(ground_terminal_representatives)[0]
            for other_ground_rep in list(ground_terminal_representatives)[1:]:
                self._dsu_union(first_ground_rep, other_ground_rep)
            if first_ground_rep:
                ground_terminal_representatives = {self._dsu_find(first_ground_rep)}

        node_rep_to_name_map = {}
        next_node_number = 1
        unified_dsu_ground_rep = None
        if ground_terminal_representatives:
            unified_dsu_ground_rep = self._dsu_find(list(ground_terminal_representatives)[0])

        all_unique_reps = sorted(
            list(set(self._dsu_find(ct_tuple) for ct_tuple in all_component_terminals_init)),
            key=lambda rep: (rep != unified_dsu_ground_rep, id(rep[0]), rep[1])
        )

        for rep in all_unique_reps:
            if rep not in node_rep_to_name_map:
                if unified_dsu_ground_rep and rep == unified_dsu_ground_rep:
                    node_rep_to_name_map[rep] = "0"
                elif not unified_dsu_ground_rep and "0" not in node_rep_to_name_map.values():
                    node_rep_to_name_map[rep] = "0"
                else:
                    node_rep_to_name_map[rep] = f"n{next_node_number}"
                    next_node_number += 1

        final_node_names_for_all_comps = {}
        for comp in self.components:
            if comp.COMPONENT_TYPE != "Wire": # Should not happen with HeadlessComponent
                terminal_ids_ordered = []
                if comp.COMPONENT_TYPE == "V": # VoltageSourceItem.TERMINAL_PLUS/MINUS are 0 and 1
                    terminal_ids_ordered = [BaseComponentItem.TERMINAL_A, BaseComponentItem.TERMINAL_B]
                else:
                    terminal_ids_ordered = sorted(list(comp.local_terminals.keys()))

                for term_id in terminal_ids_ordered:
                    if term_id not in comp.local_terminals: continue
                    representative = self._dsu_find((comp, term_id))
                    node_name = node_rep_to_name_map.get(representative, f"unmapped_{comp.name}_t{term_id}")
                    final_node_names_for_all_comps[(comp, term_id)] = node_name

        self.solution_path_output += "DSU and Node Naming Complete (Headless).\n"
        self.solution_path_output += f"Node Representative to Name Map: { {self._rep_to_str(k):v for k,v in node_rep_to_name_map.items()} }\n"
        # final_node_names_for_all_comps uses component instances as keys, need a string representation for logging
        logged_final_node_names = {}
        for (comp_inst, term_id), node_name in final_node_names_for_all_comps.items():
            logged_final_node_names[f"{comp_inst.name}_t{term_id}"] = node_name
        self.solution_path_output += f"Final Node Names for All Comps: {logged_final_node_names}\n"

        # --- Prepare data for SPICE netlist generation ---
        netlist_component_data_for_spice = []
        for comp in self.components:
            if comp.COMPONENT_TYPE != "GND": # Ground is implicit via node "0"
                comp_nodes_for_spice = []
                # Determine terminal order for SPICE
                terminal_ids_ordered = []
                if comp.COMPONENT_TYPE == "V":
                    terminal_ids_ordered = [BaseComponentItem.TERMINAL_A, BaseComponentItem.TERMINAL_B] # Plus, Minus
                else: # R, C, L
                    terminal_ids_ordered = sorted(list(comp.local_terminals.keys()))

                for term_id in terminal_ids_ordered:
                    comp_nodes_for_spice.append(final_node_names_for_all_comps[(comp, term_id)])

                netlist_component_data_for_spice.append({
                    'type': comp.COMPONENT_TYPE,
                    'name': comp.name,
                    'nodes': comp_nodes_for_spice,
                    'value': comp.get_spice_value_string() # Already adapted in HeadlessComponent
                })

        all_unique_node_names_for_spice = set(node_rep_to_name_map.values())

        # --- Generate SPICE Netlist String ---
        spice_netlist_str = self._generate_spice_netlist_string(netlist_component_data_for_spice, all_unique_node_names_for_spice)
        self.solution_path_output += "\nGenerated SPICE Netlist (Headless):\n" + spice_netlist_str + "\n"
        self.solver_log_output += "SPICE Netlist (Headless):\n" + spice_netlist_str + "\n" + "-"*20 + "\n"
        # --- End of SPICE Netlist Generation ---

        # --- Execute scs.py ---
        temp_spice_filepath = None
        temp_results_base_filepath_stem = None
        temp_dir = tempfile.gettempdir()

        try:
            fd, temp_spice_filepath = tempfile.mkstemp(suffix='.sp', prefix='headless_gui_sim_', text=True, dir=temp_dir)
            with os.fdopen(fd, 'w') as tmp_sp_file:
                tmp_sp_file.write(spice_netlist_str)
            self.temp_files_to_cleanup.append(temp_spice_filepath)

            temp_results_base_filepath_stem = os.path.join(temp_dir, os.path.splitext(os.path.basename(temp_spice_filepath))[0])

            script_dir = os.path.dirname(os.path.abspath(__file__)) # Assumes scs.py is in the same dir
            scs_script_path = os.path.join(script_dir, "scs.py")

            command = ["python", scs_script_path, "-i", temp_spice_filepath, "-o", temp_results_base_filepath_stem]

            self.solver_log_output += f"Executing command: {' '.join(command)}\nWorking Directory: {script_dir}\n"

            process = subprocess.run(command, capture_output=True, text=True, cwd=script_dir, timeout=30)

            self.solver_log_output += "Solver Standard Output:\n" + (process.stdout or "N/A") + "\n"
            self.solver_log_output += "Solver Standard Error:\n" + (process.stderr or "N/A") + "\n"

            results_filepath = temp_results_base_filepath_stem + ".results"
            log_filepath = temp_results_base_filepath_stem + ".log"
            self.temp_files_to_cleanup.extend([results_filepath, log_filepath])

            if process.returncode == 0:
                self.solver_log_output += "Simulation completed successfully (scs.py return code 0).\n"
                if os.path.exists(results_filepath):
                    with open(results_filepath, 'r') as f_results:
                        results_content = f_results.read()
                    self.solver_log_output += "\n" + "-"*10 + "Raw Results from scs.py" + "-"*10 + "\n" + results_content + "\n"
                    self._parse_measure_results(results_content) # Parse into self.parsed_measure_results
                else:
                    self.solver_log_output += f"ERROR: Results file '{results_filepath}' not found despite scs.py success.\n"
            else:
                self.solver_log_output += f"Simulation failed (scs.py return code: {process.returncode}).\n"
                if os.path.exists(log_filepath):
                    with open(log_filepath, 'r') as f_log:
                        self.solver_log_output += "\n" + "-"*10 + "Solver Log (on error from scs.py)" + "-"*10 + "\n" + f_log.read() + "\n"
                else:
                     self.solver_log_output += f"ERROR: scs.py log file '{log_filepath}' not found after failure.\n"
        except FileNotFoundError as e_fnf:
             self.solver_log_output += f"PYTHON SCRIPT ERROR: scs.py not found. {e_fnf}\n"
        except subprocess.TimeoutExpired:
            self.solver_log_output += "SIMULATION TIMEOUT: scs.py process took too long to complete.\n"
        except Exception as e:
            self.solver_log_output += f"PYTHON SCRIPT ERROR during simulation: {type(e).__name__}: {e}\n"
        # --- End of Execute scs.py ---

        # --- TODO: SymPy Analysis ---
        self.solution_path_output += "--- End of Headless Simulation (scs.py execution part done) ---\n"


    def _parse_measure_results(self, results_content_str):
        # Adapted from SchematicEditor._parse_and_display_measure_results
        # This version only populates self.parsed_measure_results dictionary
        self.parsed_measure_results.clear()
        pattern = re.compile(
            r"^(?P<name>\S+?):\s*"
            r"(?P<expr>v\([\w\.\-\+]+\)|i\([\w\.\-\+]+\)|isub\([\w\.\-\+]+\)|[\w\.\-\+]+)\s*"
            r"=\s*---------------------\s*"
            r"(?P<value>.+?)"
            r"(?=(?:\r?\n){2}\S+?:|\Z)",
            re.MULTILINE | re.DOTALL
        )
        matches_found = 0
        for match in pattern.finditer(results_content_str):
            matches_found += 1
            data = match.groupdict()
            # name_str = data['name'].strip() # Measurement name, not used directly for parsed_measure_results keys
            expr_str = data['expr'].strip()
            value_str = data['value'].strip().replace("\n", " ")
            if expr_str.startswith("v(") and expr_str.endswith(")"):
                self.parsed_measure_results[expr_str] = value_str

        if matches_found == 0:
            self.solver_log_output += "No .measure results found in the scs.py output to parse.\n"
        else:
            self.solver_log_output += f"Parsed {len(self.parsed_measure_results)} v(node) results from scs.py output.\n"


    def _generate_spice_netlist_string(self, netlist_component_data, all_unique_node_names_for_spice):
        # Adapted from SchematicEditor._generate_spice_netlist_string
        spice_lines = ["* Auto-generated SPICE netlist from HeadlessSimulator"]

        components_added_to_netlist = False
        for comp_data in netlist_component_data:
            # GroundComponentItem type components are not explicitly added to netlist here
            # Their effect is through the node "0" naming from DSU.
            if comp_data['type'] != "GND": # This check is technically redundant if GND components are pre-filtered
                nodes_str = " ".join(comp_data['nodes'])
                spice_lines.append(f"{comp_data['name']} {nodes_str} {comp_data['value']}")
                components_added_to_netlist = True

        if not components_added_to_netlist: # Covers truly empty or only-ground circuits
             spice_lines.append("* Empty circuit or only ground symbols present.")

        # Add .measure statements for all unique node voltages
        for node_name in sorted(list(all_unique_node_names_for_spice)):
            sanitized_node_name = re.sub(r'[^a-zA-Z0-9_]', '_', node_name)
            spice_lines.append(f".measure dc gui_v_{sanitized_node_name} v({node_name})")

        # Add AC analysis line if parameters are set (self.ac_analysis_params)
        if self.ac_analysis_params:
            ac = self.ac_analysis_params
            try: # Basic validation for AC params
                float(ac['points']); float(parse_value_with_si_suffix(ac['fstart'])); float(parse_value_with_si_suffix(ac['fstop']))
                spice_lines.append(f".ac {ac['type']} {ac['points']} {ac['fstart']} {ac['fstop']}")
                for node_name in sorted(list(all_unique_node_names_for_spice)):
                    sanitized_node_name = re.sub(r'[^a-zA-Z0-9_]', '_', node_name)
                    spice_lines.append(f".measure ac gui_vac_{sanitized_node_name} v({node_name})")
            except (ValueError, KeyError) as e:
                 self.solver_log_output += f"Warning: Invalid AC parameters ({e}). .ac line not added.\n"

        # spice_lines.append(".end") # scs.py parser does not handle .end for main circuit, expects EOF.
        return "\n".join(spice_lines)

    def _dsu_find(self, item_terminal_tuple): # Added as method to HeadlessSimulator
        if not isinstance(item_terminal_tuple, tuple) or len(item_terminal_tuple) != 2:
            return item_terminal_tuple
        if item_terminal_tuple not in self.dsu_parent:
            self.dsu_parent[item_terminal_tuple] = item_terminal_tuple

        path = []
        current = item_terminal_tuple
        while self.dsu_parent[current] != current:
            path.append(current)
            current = self.dsu_parent[current]
        for node_in_path in path:
            self.dsu_parent[node_in_path] = current
        return current

    def _dsu_union(self, tuple1, tuple2): # Added as method to HeadlessSimulator
        root1 = self._dsu_find(tuple1)
        root2 = self._dsu_find(tuple2)
        if root1 != root2:
            self.dsu_parent[root2] = root1

    def _rep_to_str(self, rep_tuple): # Helper for logging complex keys
        comp_inst, term_id = rep_tuple
        return f"({comp_inst.name}_obj_at_{hex(id(comp_inst))}, t{term_id})"


    def _cleanup_temp_files(self): # Copied from SchematicEditor
        cleaned_count = 0
        for filepath in list(self.temp_files_to_cleanup):
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
                    cleaned_count +=1
                if filepath in self.temp_files_to_cleanup:
                    self.temp_files_to_cleanup.remove(filepath)
            except OSError as e:
                print(f"Warning: Could not delete temporary file {filepath}: {e}")
        if cleaned_count > 0:
             print(f"Cleaned up {cleaned_count} temporary simulation files.")
# --- End of Headless Simulation Logic ---


def main():
    diag_output_filename = "diagnostic_output.txt"
    is_headless_test = os.environ.get("RUN_HEADLESS_TEST") == "true"

    app = None
    editor = None # GUI editor
    headless_sim = None # Headless simulator instance

    print(f"Diagnostic output will be written to: {os.path.abspath(diag_output_filename)}")
    if is_headless_test:
        print("RUN_HEADLESS_TEST is true. Attempting to run in headless mode.")

    try:
        with open(diag_output_filename, "w") as diag_file:
            diag_file.write(f"Starting diagnostic run... Headless test: {is_headless_test}\n")
            diag_file.flush()

            if is_headless_test:
                diag_file.write("Instantiating HeadlessSimulator...\n")
                diag_file.flush()
                headless_sim = HeadlessSimulator()
                diag_file.write("HeadlessSimulator instantiated.\n")
                diag_file.flush()

                test_circuit_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_circuits", "voltage_divider_symbolic.json")
                diag_file.write(f"Looking for test circuit at: {test_circuit_path}\n")
                diag_file.flush()

                if os.path.exists(test_circuit_path):
                    diag_file.write(f"Headless: Attempting to auto-load test circuit: {test_circuit_path}\n")
                    diag_file.flush()
                    if headless_sim.load_circuit_data(test_circuit_path):
                        diag_file.write("Headless: Test circuit loaded, attempting to run simulation...\n")
                        diag_file.flush()
                        headless_sim.run_simulation() # This is currently a placeholder
                        diag_file.write("Headless: Simulation run completed (placeholder).\n")
                        diag_file.flush()
                    else:
                        diag_file.write("Headless: Failed to load circuit data.\n")
                        diag_file.flush()

                    diag_file.write("\n--- Headless Solver Log ---\n")
                    diag_file.write(headless_sim.solver_log_output + "\n")
                    diag_file.write("\n--- Headless Solution Path & Analysis ---\n")
                    diag_file.write(headless_sim.solution_path_output + "\n")
                    diag_file.write("\n--- Headless Parsed Measure Results ---\n")
                    diag_file.write(json.dumps(headless_sim.parsed_measure_results, indent=2) + "\n")
                    diag_file.write("\n--- End of Headless Auto-Run Output ---\n")
                    diag_file.flush()
                else:
                    diag_file.write(f"Test circuit file not found: {test_circuit_path}\n")
                    diag_file.flush()

                diag_file.write("Headless diagnostic logging complete.\n")
                diag_file.flush()

            else: # Not headless, normal GUI mode
                diag_file.write("Attempting to instantiate QApplication for GUI mode...\n")
                diag_file.flush()
                app = QApplication(sys.argv)
                diag_file.write("QApplication instantiated for GUI mode.\n")
                diag_file.flush()

                diag_file.write("Attempting to instantiate SchematicEditor for GUI mode...\n")
                diag_file.flush()
                editor = SchematicEditor()
                diag_file.write("SchematicEditor instantiated for GUI mode.\n")
                diag_file.flush()

                # The original auto-load for GUI mode was removed, can be added back if needed
                # For now, GUI mode will start with an empty editor.
                diag_file.write("GUI mode: Setup complete. Attempting to show GUI...\n")
                diag_file.flush()


    except Exception as e:
        try:
            with open(diag_output_filename, "a") as diag_file_exc:
                diag_file_exc.write(f"\n!!! EXCEPTION DURING MAIN SETUP/RUN: {type(e).__name__}: {e} !!!\n")
                import traceback
                traceback.print_exc(file=diag_file_exc)
                diag_file_exc.flush()
        except Exception as e_nested:
            print(f"Nested exception while writing main exception to diag file: {type(e_nested).__name__}: {e_nested}")
        print(f"EXCEPTION DURING MAIN SETUP/RUN: {type(e).__name__}: {e}")


    if is_headless_test:
        if headless_sim: headless_sim._cleanup_temp_files() # Clean up if sim ran
        print("RUN_HEADLESS_TEST is true. Exiting cleanly after diagnostic file write.")
        sys.exit(0)

    if app and editor:
        editor.show()
        sys.exit(app.exec_())
    else:
        print("QApplication or SchematicEditor not initialized for GUI mode. Exiting.")
        sys.exit(1)


if __name__ == '__main__':
    main()
