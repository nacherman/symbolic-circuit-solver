import sys
import json
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QTextEdit, QListWidget, QListWidgetItem, QDockWidget, QGraphicsView,
                             QGraphicsScene, QGraphicsItem, QFrame, QLabel, QFormLayout, QLineEdit,
                             QMenuBar, QAction, QFileDialog, QMessageBox) # Added QMessageBox
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QDrag, QPolygonF, QFont
from PyQt5.QtCore import Qt, QRectF, QPointF, QMimeData, QLineF
import pprint

# --- Component and Wire Classes ---
class ResistorItem(QGraphicsItem):
    item_counter = 0
    TERMINAL_1 = 0; TERMINAL_2 = 1; COMPONENT_TYPE = "Resistor"
    def __init__(self, name=None, value="1k", parent=None):
        super().__init__(parent)
        if name is None:
            ResistorItem.item_counter += 1; self._name = f"R{ResistorItem.item_counter}"
        else: self._name = name
        self._value = value
        self.setFlag(QGraphicsItem.ItemIsSelectable); self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges) # For position and rotation updates
        self.width = 60; self.height = 30; self.lead_length = 20
        self.terminal_radius = 4; self.snap_radius = 10
        self.font = QFont("Arial", 8)
        self.local_terminals = {
            self.TERMINAL_1: QPointF(-self.width / 2 - self.lead_length, 0),
            self.TERMINAL_2: QPointF(self.width / 2 + self.lead_length, 0)
        }
        self.terminal_connections = {self.TERMINAL_1: [], self.TERMINAL_2: []}
    @property
    def name(self): return self._name
    def set_name(self, new_name):
        if self._name != new_name:
            # Scene might need to update its mapping if name is used as key
            if self.scene() and hasattr(self.scene(), 'component_name_changed'):
                self.scene().component_name_changed(self, new_name)
            self.prepareGeometryChange(); self._name = new_name; self.update()
    @property
    def value(self): return self._value
    def set_value(self, new_value):
        if self._value != new_value: self.prepareGeometryChange(); self._value = new_value; self.update()

    def boundingRect(self):
        text_height_offset = 18
        max_x_extent = self.width / 2 + self.lead_length + self.terminal_radius
        max_y_extent = self.height / 2 + text_height_offset + self.terminal_radius
        outer_dim = max(max_x_extent, max_y_extent)
        bounding_size = outer_dim * 2 * 1.1
        return QRectF(-bounding_size / 2, -bounding_size / 2, bounding_size, bounding_size)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing); painter.setFont(self.font)
        body_rect = QRectF(-self.width / 2, -self.height / 2, self.width, self.height)
        painter.setPen(QPen(Qt.black, 2)); painter.setBrush(QBrush(Qt.white)); painter.drawRect(body_rect)
        painter.setPen(Qt.black)
        name_y_pos = body_rect.top() - painter.fontMetrics().height() - 2
        painter.drawText(QRectF(body_rect.left(), name_y_pos, body_rect.width(), painter.fontMetrics().height()), Qt.AlignCenter, self.name)
        value_y_pos = body_rect.bottom() + 2
        painter.drawText(QRectF(body_rect.left(), value_y_pos, body_rect.width(), painter.fontMetrics().height()), Qt.AlignCenter, self.value)
        painter.setPen(QPen(Qt.black, 2))
        painter.drawLine(QPointF(-self.width / 2, 0), self.local_terminals[self.TERMINAL_1])
        painter.drawLine(QPointF(self.width / 2, 0), self.local_terminals[self.TERMINAL_2])
        terminal_brush = QBrush(Qt.black); painter.setPen(QPen(Qt.black, 1)); painter.setBrush(terminal_brush)
        for t_pos in self.local_terminals.values(): painter.drawEllipse(t_pos, self.terminal_radius, self.terminal_radius)
        if self.isSelected():
            pen = QPen(Qt.blue, 1, Qt.DashLine); painter.setPen(pen); painter.setBrush(Qt.NoBrush)
            selection_padding = 3
            highlight_rect = QRectF(-self.width/2 - self.lead_length - selection_padding, -self.height/2 - selection_padding,
                                   self.width + 2*self.lead_length + 2*selection_padding, self.height + 2*selection_padding)
            painter.drawRect(highlight_rect)

    def rotate_item(self, angle_degrees=90): self.setRotation(self.rotation() + angle_degrees)
    def get_terminal_scene_positions(self): return {tid: self.mapToScene(pos) for tid, pos in self.local_terminals.items()}
    def connect_wire(self, terminal_id, wire_item):
        if terminal_id in self.terminal_connections:
            if wire_item not in self.terminal_connections[terminal_id]: self.terminal_connections[terminal_id].append(wire_item)
    def disconnect_wire(self, terminal_id, wire_item):
        if terminal_id in self.terminal_connections and wire_item in self.terminal_connections[terminal_id]:
            self.terminal_connections[terminal_id].remove(wire_item)
    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged or change == QGraphicsItem.ItemRotationHasChanged:
            for wire_list in self.terminal_connections.values(): # Iterate through lists of wires for all terminals
                for wire in wire_list:
                    if hasattr(wire, 'update_endpoints_from_connections'):
                        wire.update_endpoints_from_connections()
        return super().itemChange(change, value)

class WireItem(QGraphicsItem):
    COMPONENT_TYPE = "Wire"
    def __init__(self, start_conn=None, end_conn=None, parent=None):
        super().__init__(parent)
        self.start_connection = start_conn
        self.end_connection = end_conn
        self.setFlag(QGraphicsItem.ItemIsSelectable); self.setZValue(-1)
        self._p1_scene = QPointF(); self._p2_scene = QPointF()
        self.update_endpoints_from_connections()
    def update_endpoints_from_connections(self):
        p1, p2 = QPointF(), QPointF()
        # Check if component item and local_terminals attribute exist before accessing
        if self.start_connection:
            comp_item, term_id = self.start_connection
            if comp_item and comp_item.scene() and hasattr(comp_item, 'local_terminals') and term_id in comp_item.local_terminals:
                 p1 = comp_item.mapToScene(comp_item.local_terminals[term_id])
        if self.end_connection:
            comp_item, term_id = self.end_connection
            if comp_item and comp_item.scene() and hasattr(comp_item, 'local_terminals') and term_id in comp_item.local_terminals:
                p2 = comp_item.mapToScene(comp_item.local_terminals[term_id])

        if self._p1_scene != p1 or self._p2_scene != p2:
            self.prepareGeometryChange(); self._p1_scene = p1; self._p2_scene = p2; self.update()
    def get_scene_points(self): return self._p1_scene, self._p2_scene
    def boundingRect(self):
        if self._p1_scene.isNull() and self._p2_scene.isNull(): return QRectF()
        return QRectF(self.mapFromScene(self._p1_scene), self.mapFromScene(self._p2_scene)).normalized().adjusted(-5,-5,5,5)
    def paint(self, painter, option, widget=None):
        if self._p1_scene.isNull() or self._p2_scene.isNull(): return
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(Qt.darkCyan, 2)
        if self.isSelected(): pen.setColor(Qt.blue); pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.drawLine(self.mapFromScene(self._p1_scene), self.mapFromScene(self._p2_scene))
    def cleanup_connections(self):
        if self.start_connection:
            comp, term_id = self.start_connection
            if hasattr(comp, 'disconnect_wire'): comp.disconnect_wire(term_id, self)
        if self.end_connection:
            comp, term_id = self.end_connection
            if hasattr(comp, 'disconnect_wire'): comp.disconnect_wire(term_id, self)
        self.start_connection = None; self.end_connection = None
        self.update_endpoints_from_connections() # Wire becomes 'null'

class SchematicView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setAcceptDrops(True); self.current_tool = None
        self.wiring_start_connection = None
        self.temp_line_item = None
        self.snapped_connection_end_info = None
    def set_tool(self, tool_name):
        self.current_tool = tool_name; self.wiring_start_connection = None; self.snapped_connection_end_info = None
        if self.temp_line_item: self.scene().removeItem(self.temp_line_item); self.temp_line_item = None
        self.setCursor(Qt.CrossCursor if tool_name == "Wire" else Qt.ArrowCursor)
    def _get_snapped_connection_info(self, scene_pos_check):
        for item in self.scene().items():
            if isinstance(item, ResistorItem): # Extend for other types
                term_positions_scene = item.get_terminal_scene_positions()
                for term_id, term_scene_pos in term_positions_scene.items():
                    if (term_scene_pos - scene_pos_check).manhattanLength() < item.snap_radius * 1.5:
                        return item, term_id, term_scene_pos
        return None
    def mousePressEvent(self, event):
        scene_pos = self.mapToScene(event.pos())
        if self.current_tool == "Wire":
            if event.button() == Qt.LeftButton:
                snapped_data = self._get_snapped_connection_info(scene_pos)
                if self.wiring_start_connection is None:
                    if snapped_data:
                        item, term_id, term_scene_pos = snapped_data
                        self.wiring_start_connection = (item, term_id)
                        self.temp_line_item = self.scene().addLine(QLineF(term_scene_pos, term_scene_pos), QPen(Qt.darkGray, 1, Qt.DashLine))
                else:
                    end_connection_tuple = None
                    if self.snapped_connection_end_info:
                        item, term_id, _ = self.snapped_connection_end_info
                        end_connection_tuple = (item, term_id)
                    elif snapped_data :
                        item, term_id, _ = snapped_data
                        end_connection_tuple = (item, term_id)
                    if end_connection_tuple and end_connection_tuple != self.wiring_start_connection:
                        wire = WireItem(self.wiring_start_connection, end_connection_tuple)
                        self.scene().addItem(wire)
                        start_comp, start_term_id = self.wiring_start_connection
                        end_comp, end_term_id = end_connection_tuple
                        if hasattr(start_comp, 'connect_wire'): start_comp.connect_wire(start_term_id, wire)
                        if hasattr(end_comp, 'connect_wire'): end_comp.connect_wire(end_term_id, wire)
                    self.wiring_start_connection = None
                    if self.temp_line_item: self.scene().removeItem(self.temp_line_item); self.temp_line_item = None
                    self.snapped_connection_end_info = None
            elif event.button() == Qt.RightButton:
                self.wiring_start_connection = None; self.snapped_connection_end_info = None
                if self.temp_line_item: self.scene().removeItem(self.temp_line_item); self.temp_line_item = None
                self.set_tool(None)
        else: super().mousePressEvent(event)
    def mouseMoveEvent(self, event):
        scene_pos = self.mapToScene(event.pos())
        if self.current_tool == "Wire" and self.wiring_start_connection:
            start_comp, start_term_id = self.wiring_start_connection
            if not start_comp.scene():
                self.wiring_start_connection = None; self.snapped_connection_end_info = None
                if self.temp_line_item: self.scene().removeItem(self.temp_line_item); self.temp_line_item = None
                self.set_tool(None); return
            start_draw_pos = start_comp.mapToScene(start_comp.local_terminals[start_term_id])
            snapped_data = self._get_snapped_connection_info(scene_pos)
            if snapped_data:
                item, term_id, term_scene_pos = snapped_data
                self.snapped_connection_end_info = (item, term_id)
                display_end_point = term_scene_pos
            else: self.snapped_connection_end_info = None; display_end_point = scene_pos
            if self.temp_line_item: self.temp_line_item.setLine(QLineF(start_draw_pos, display_end_point))
        else: super().mouseMoveEvent(event)
    def keyPressEvent(self, event):
        selected_items = self.scene().selectedItems()
        if event.key() == Qt.Key_R:
            for item in selected_items:
                if hasattr(item, 'rotate_item'): item.rotate_item(90)
        elif event.key() == Qt.Key_Delete or event.key() == Qt.Key_Backspace:
            items_to_delete = list(selected_items)
            for item in items_to_delete:
                if isinstance(item, WireItem): item.cleanup_connections()
                elif isinstance(item, ResistorItem):
                    for term_id in list(item.terminal_connections.keys()):
                        for wire in list(item.terminal_connections[term_id]):
                            if wire.scene(): self.scene().removeItem(wire)
                            wire.cleanup_connections()
                if item.scene(): self.scene().removeItem(item)
        elif event.key() == Qt.Key_Escape:
            if self.current_tool == "Wire":
                self.wiring_start_connection = None; self.snapped_connection_end_info = None
                if self.temp_line_item: self.scene().removeItem(self.temp_line_item); self.temp_line_item = None
            self.set_tool(None)
        else: super().keyPressEvent(event)
    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-componentname"):
            component_name = event.mimeData().data("application/x-componentname").data().decode('utf-8')
            if component_name != "Wire": self.set_tool(None); event.acceptProposedAction()
            else: event.ignore()
        else: super().dragEnterEvent(event)
    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-componentname"): event.acceptProposedAction()
        else: super().dragMoveEvent(event)
    def dropEvent(self, event):
        if event.mimeData().hasFormat("application/x-componentname"):
            component_name = event.mimeData().data("application/x-componentname").data().decode('utf-8')
            if component_name == "Wire": event.ignore(); return
            drop_pos = self.mapToScene(event.pos())
            if component_name == "Resistor":
                item = ResistorItem(); item.setPos(drop_pos); self.scene().addItem(item)
            event.acceptProposedAction()
        else: super().dropEvent(event)
        self.set_tool(None)

class ComponentListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.setDragEnabled(True)
        self.addItems(["Resistor", "Voltage Source", "Capacitor", "Inductor", "Wire"])
        self.itemClicked.connect(self.on_item_clicked); self.schematic_view_ref = None
    def set_schematic_view(self, view): self.schematic_view_ref = view
    def on_item_clicked(self, item):
        if self.schematic_view_ref:
            if item.text() == "Wire": self.schematic_view_ref.set_tool("Wire")
            else:
                if self.schematic_view_ref.current_tool == "Wire": self.schematic_view_ref.set_tool(None)
    def startDrag(self, supportedActions):
        item = self.currentItem()
        if item and item.text() != "Wire":
            mime_data = QMimeData(); mime_data.setData("application/x-componentname", item.text().encode('utf-8'))
            drag = QDrag(self); drag.setMimeData(mime_data)
            if self.schematic_view_ref and self.schematic_view_ref.current_tool == "Wire": self.schematic_view_ref.set_tool(None)
            drag.exec_(supportedActions)
        else: super().startDrag(Qt.IgnoreAction)

class PropertiesWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.layout = QFormLayout(self); self.current_item = None
        self.name_edit = QLineEdit(); self.value_edit = QLineEdit()
        self.layout.addRow("Name:", self.name_edit); self.layout.addRow("Value:", self.value_edit)
        self.name_edit.editingFinished.connect(self.on_name_changed)
        self.value_edit.editingFinished.connect(self.on_value_changed)
    def set_current_item(self, item):
        self.current_item = item
        if isinstance(item, ResistorItem):
            self.name_edit.setText(item.name); self.value_edit.setText(item.value)
            self.name_edit.setEnabled(True); self.value_edit.setEnabled(True)
        else:
            self.name_edit.setText(""); self.value_edit.setText("")
            self.name_edit.setEnabled(False); self.value_edit.setEnabled(False)
    def on_name_changed(self):
        if self.current_item and isinstance(self.current_item, ResistorItem):
            if self.current_item.name != self.name_edit.text(): self.current_item.set_name(self.name_edit.text())
    def on_value_changed(self):
        if self.current_item and isinstance(self.current_item, ResistorItem):
            if self.current_item.value != self.value_edit.text(): self.current_item.set_value(self.value_edit.text())

class SchematicEditor(QMainWindow):
    def __init__(self):
        super().__init__(); self.current_filename = None; self.initUI()
    def initUI(self):
        self.setWindowTitle('Symbolic Circuit Solver - Schematic Editor'); self.setGeometry(100, 100, 1600, 900)
        self.scene = QGraphicsScene(self); self.scene.setSceneRect(-400, -300, 800, 600)
        self.scene.selectionChanged.connect(self.on_scene_selection_changed)
        self.schematic_view = SchematicView(self.scene, self)
        self.schematic_view.setFrameShape(QFrame.StyledPanel); self.schematic_view.setRenderHint(QPainter.Antialiasing)
        self.setCentralWidget(self.schematic_view)
        component_dock = QDockWidget("Components", self)
        self.component_list = ComponentListWidget(); self.component_list.set_schematic_view(self.schematic_view)
        component_dock.setWidget(self.component_list); self.addDockWidget(Qt.LeftDockWidgetArea, component_dock)
        properties_dock = QDockWidget("Properties", self)
        self.properties_widget = PropertiesWidget()
        properties_dock.setWidget(self.properties_widget); self.addDockWidget(Qt.RightDockWidgetArea, properties_dock)
        self.properties_widget.set_current_item(None)
        output_dock = QDockWidget("Output & Formulas", self)
        self.output_area = QTextEdit(); self.output_area.setReadOnly(True)
        output_dock.setWidget(self.output_area); self.addDockWidget(Qt.BottomDockWidgetArea, output_dock)
        menubar = self.menuBar()
        file_menu = menubar.addMenu('&File')
        open_action = QAction('&Open Circuit...', self); open_action.setShortcut('Ctrl+O')
        open_action.triggered.connect(self.open_circuit); file_menu.addAction(open_action)
        save_action = QAction('&Save Circuit', self); save_action.setShortcut('Ctrl+S')
        save_action.triggered.connect(self.save_circuit); file_menu.addAction(save_action)
        save_as_action = QAction('Save Circuit &As...', self); save_as_action.setShortcut('Ctrl+Shift+S')
        save_as_action.triggered.connect(self.save_circuit_as); file_menu.addAction(save_as_action)
        file_menu.addSeparator()
        exit_action = QAction('&Exit', self); exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close); file_menu.addAction(exit_action)
        circuit_menu = menubar.addMenu('&Circuit')
        generate_netlist_action = QAction('&Generate Netlist (Internal)', self)
        generate_netlist_action.triggered.connect(self.generate_internal_netlist)
        circuit_menu.addAction(generate_netlist_action)
        self.statusBar().showMessage('Ready.')

    def on_scene_selection_changed(self):
        selected_items = self.scene.selectedItems()
        if len(selected_items) == 1 and isinstance(selected_items[0], (ResistorItem)):
             self.properties_widget.set_current_item(selected_items[0])
        else: self.properties_widget.set_current_item(None)

    def generate_internal_netlist(self):
        self.output_area.clear()
        components_on_scene = [item for item in self.scene.items() if hasattr(item, 'COMPONENT_TYPE') and item.COMPONENT_TYPE != WireItem.COMPONENT_TYPE]
        wires_on_scene = [item for item in self.scene.items() if hasattr(item, 'COMPONENT_TYPE') and item.COMPONENT_TYPE == WireItem.COMPONENT_TYPE]
        if not components_on_scene: self.output_area.setText("No components on schematic."); return
        parent = {}
        def find_set(item_term_tuple):
            if item_term_tuple not in parent: parent[item_term_tuple] = item_term_tuple
            if parent[item_term_tuple] == item_term_tuple: return item_term_tuple
            parent[item_term_tuple] = find_set(parent[item_term_tuple]); return parent[item_term_tuple]
        def unite_sets(item_term_tuple1, item_term_tuple2):
            root1 = find_set(item_term_tuple1); root2 = find_set(item_term_tuple2)
            if root1 != root2: parent[root2] = root1
        for comp in components_on_scene:
            if hasattr(comp, 'local_terminals'):
                for term_id in comp.local_terminals.keys(): find_set((comp, term_id))
        for wire in wires_on_scene:
            if wire.start_connection and wire.end_connection:
                start_comp, _ = wire.start_connection; end_comp, _ = wire.end_connection
                if start_comp.scene() and end_comp.scene(): unite_sets(wire.start_connection, wire.end_connection)
        node_map = {}; next_node_idx = 0
        for comp in components_on_scene:
            if hasattr(comp, 'local_terminals'):
                for term_id in comp.local_terminals.keys():
                    representative = find_set((comp, term_id))
                    if representative not in node_map: node_map[representative] = f"n{next_node_idx}"; next_node_idx += 1
        netlist_components_data = []
        for comp in components_on_scene:
            if isinstance(comp, ResistorItem):
                try:
                    conn1 = (comp, ResistorItem.TERMINAL_1); conn2 = (comp, ResistorItem.TERMINAL_2)
                    node1_rep = find_set(conn1) if conn1 in parent else None
                    node2_rep = find_set(conn2) if conn2 in parent else None
                    node1_name = node_map.get(node1_rep, "unconnected")
                    node2_name = node_map.get(node2_rep, "unconnected")
                    netlist_components_data.append({'type': comp.COMPONENT_TYPE, 'name': comp.name,
                                                    'nodes': [node1_name, node2_name], 'value': comp.value})
                except Exception as e: self.output_area.append(f"Error processing component {comp.name}: {e}")
        output_str = "Internal Netlist Data:\n"; output_str += pprint.pformat(netlist_components_data)
        self.output_area.setText(output_str); self.statusBar().showMessage('Internal netlist generated.')

    def save_circuit_as(self):
        options = QFileDialog.Options(); options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getSaveFileName(self, "Save Circuit As", self.current_filename or "", "Circuit Files (*.json);;All Files (*)", options=options)
        if filename: self.current_filename = filename; self.save_circuit_to_file(filename)
        else: self.statusBar().showMessage("Save cancelled.", 2000)

    def save_circuit(self):
        if self.current_filename: self.save_circuit_to_file(self.current_filename)
        else: self.save_circuit_as()

    def save_circuit_to_file(self, filename):
        circuit_data = {'components': [], 'wires': []}
        # For loading, ensure component names are unique or use another persistent ID
        # Saving by name for this iteration
        for item in self.scene.items():
            if hasattr(item, 'COMPONENT_TYPE'):
                if item.COMPONENT_TYPE != WireItem.COMPONENT_TYPE:
                    circuit_data['components'].append({
                        'type': item.COMPONENT_TYPE, 'name': item.name, 'value': item.value, # Assumes name & value properties exist
                        'pos_x': item.pos().x(), 'pos_y': item.pos().y(), 'rotation': item.rotation()
                    })
                elif item.COMPONENT_TYPE == WireItem.COMPONENT_TYPE:
                    start_comp_name, end_comp_name = None, None
                    start_term_id, end_term_id = None, None
                    if item.start_connection:
                        start_comp_name = item.start_connection[0].name; start_term_id = item.start_connection[1]
                    if item.end_connection:
                        end_comp_name = item.end_connection[0].name; end_term_id = item.end_connection[1]
                    circuit_data['wires'].append({
                        'type': item.COMPONENT_TYPE,
                        'start_comp_name': start_comp_name, 'start_term_id': start_term_id,
                        'end_comp_name': end_comp_name, 'end_term_id': end_term_id
                    })
        try:
            with open(filename, 'w') as f: json.dump(circuit_data, f, indent=4)
            self.statusBar().showMessage(f"Circuit saved to {filename}", 5000)
        except Exception as e: self.statusBar().showMessage(f"Error saving file: {e}", 5000)

    def open_circuit(self):
        options = QFileDialog.Options(); options |= QFileDialog.DontUseNativeDialog
        filename, _ = QFileDialog.getOpenFileName(self, "Open Circuit", self.current_filename or "", "Circuit Files (*.json);;All Files (*)", options=options)
        if not filename: self.statusBar().showMessage("Open cancelled.", 2000); return

        try:
            with open(filename, 'r') as f: circuit_data = json.load(f)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open or parse file: {e}")
            self.statusBar().showMessage(f"Error opening/parsing file: {e}", 5000); return

        self.scene.clear(); self.properties_widget.set_current_item(None) # Use set_current_item
        ResistorItem.item_counter = 0 # Reset for new default names

        loaded_items_by_name = {}

        for comp_data in circuit_data.get('components', []):
            comp_type = comp_data.get('type')
            item = None
            # Use name from file, value from file for ResistorItem
            if comp_type == ResistorItem.COMPONENT_TYPE:
                item = ResistorItem(name=comp_data.get('name'), value=comp_data.get('value'))
            # Add elif for other component types like VoltageSourceItem, etc.

            if item:
                item.setPos(QPointF(comp_data.get('pos_x', 0), comp_data.get('pos_y', 0)))
                item.setRotation(comp_data.get('rotation', 0))
                self.scene.addItem(item)
                loaded_items_by_name[item.name] = item
            else:
                print(f"Warning: Unknown component type '{comp_type}' in save file.")


        for wire_data in circuit_data.get('wires', []):
            start_comp_name = wire_data.get('start_comp_name')
            start_term_id = wire_data.get('start_term_id')
            end_comp_name = wire_data.get('end_comp_name')
            end_term_id = wire_data.get('end_term_id')

            start_comp = loaded_items_by_name.get(start_comp_name)
            end_comp = loaded_items_by_name.get(end_comp_name)

            if start_comp and end_comp and start_term_id is not None and end_term_id is not None:
                # Basic validation of terminal IDs (assuming 0 or 1 for ResistorItem)
                if not (hasattr(start_comp, 'local_terminals') and start_term_id in start_comp.local_terminals):
                    print(f"Warning: Invalid start_terminal_id '{start_term_id}' for component '{start_comp_name}'. Skipping wire.")
                    continue
                if not (hasattr(end_comp, 'local_terminals') and end_term_id in end_comp.local_terminals):
                    print(f"Warning: Invalid end_terminal_id '{end_term_id}' for component '{end_comp_name}'. Skipping wire.")
                    continue

                start_conn = (start_comp, start_term_id)
                end_conn = (end_comp, end_term_id)

                wire = WireItem(start_conn, end_conn)
                self.scene.addItem(wire)
                if hasattr(start_comp, 'connect_wire'): start_comp.connect_wire(start_term_id, wire)
                if hasattr(end_comp, 'connect_wire'): end_comp.connect_wire(end_term_id, wire)
            else:
                print(f"Warning: Could not fully connect wire due to missing component reference or terminal ID: {wire_data}")

        self.current_filename = filename
        self.statusBar().showMessage(f"Circuit loaded from {filename}", 5000)


def main():
    app = QApplication(sys.argv); editor = SchematicEditor(); editor.show(); sys.exit(app.exec_())
if __name__ == '__main__': main()
