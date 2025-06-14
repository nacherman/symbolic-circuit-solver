import sys
import json
import pprint
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
    if not value_str: return value_str
    for suffix, multiplier in SI_SUFFIX_TO_MULTIPLIER.items():
        if value_str.endswith(suffix):
            try:
                numeric_part = float(value_str[:-len(suffix)])
                return numeric_part * multiplier
            except ValueError: return value_str
    try: return float(value_str)
    except ValueError: return value_str

class BaseComponentItem(QGraphicsItem):
    item_counters = {}
    TERMINAL_A = 0; TERMINAL_B = 1
    def __init__(self, name=None, value="1", default_prefix="X", num_terminals=2, parent=None):
        super().__init__(parent)
        # COMPONENT_TYPE must be defined in subclasses (e.g., "R", "V")
        component_type = self.COMPONENT_TYPE
        if component_type not in BaseComponentItem.item_counters: BaseComponentItem.item_counters[component_type] = 0

        actual_prefix = default_prefix
        if hasattr(self, 'COMPONENT_TYPE') and len(self.COMPONENT_TYPE) == 1:
            actual_prefix = self.COMPONENT_TYPE

        if name is None:
            BaseComponentItem.item_counters[component_type] += 1
            self._name=f"{actual_prefix}{BaseComponentItem.item_counters[component_type]}"
        else: self._name = name

        self._value = value
        self.setFlag(QGraphicsItem.ItemIsSelectable); self.setFlag(QGraphicsItem.ItemIsMovable); self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.font=QFont("Arial",8); self.terminal_radius=4; self.snap_radius=10; self.width=60; self.height=30; self.lead_length=20
        self.local_terminals={}; self.terminal_connections={}
        for i in range(num_terminals): self.terminal_connections[i]=[]

    @property
    def name(self): return self._name
    def set_name(self, new_name):
        new_name_stripped = str(new_name).strip().replace(" ","_")
        if not (re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", new_name_stripped) or new_name_stripped == "0") and new_name_stripped :
             main_window = self.scene().views()[0].window() if self.scene() and self.scene().views() else None
             if main_window: QMessageBox.warning(main_window, "Invalid Name", "Component name must be a valid SPICE identifier (letters, numbers, underscores, starting with letter/underscore). Cannot be purely numeric unless '0'.")
             return False
        if not new_name_stripped and self.COMPONENT_TYPE != "GND" :
             main_window = self.scene().views()[0].window() if self.scene() and self.scene().views() else None
             if main_window: QMessageBox.warning(main_window, "Invalid Name", "Component name cannot be empty.")
             return False
        if self._name != new_name_stripped: self.prepareGeometryChange(); self._name = new_name_stripped; self.update()
        return True

    @property
    def value(self): return self._value
    def set_value(self, new_value):
        new_value_str=str(new_value)
        if self._value != new_value_str: self.prepareGeometryChange(); self._value = new_value_str; self.update()
        return True

    def common_paint_logic(self, painter, show_plus_minus=False):
        painter.setFont(self.font); text_y_offset=self.height/2+5
        name_rect=QRectF(-self.width/2,-text_y_offset-10,self.width,15); value_rect=QRectF(-self.width/2,text_y_offset-5,self.width,15)
        painter.setPen(Qt.black); painter.drawText(name_rect,Qt.AlignCenter|Qt.AlignBottom,self.name)
        display_value_str = ""
        vs_item = self if self.COMPONENT_TYPE == "V" else None
        if self.COMPONENT_TYPE == "GND": pass
        elif vs_item: display_value_str = f"AC:{vs_item.ac_magnitude}V {vs_item.ac_phase}deg (DC {vs_item.value}V)" if vs_item.source_type=="AC" else f"DC:{vs_item.value}V"
        else: display_value_str = self.value
        painter.drawText(value_rect,Qt.AlignCenter|Qt.AlignTop,display_value_str)
        terminal_brush=QBrush(Qt.black); painter.setPen(QPen(Qt.black,1)); painter.setBrush(terminal_brush)
        for t_pos in self.local_terminals.values(): painter.drawEllipse(t_pos,self.terminal_radius,self.terminal_radius)
        if show_plus_minus and hasattr(self,'TERMINAL_PLUS') and hasattr(self,'TERMINAL_MINUS') and self.TERMINAL_PLUS in self.local_terminals and self.TERMINAL_MINUS in self.local_terminals:
            plus_pos=self.local_terminals[self.TERMINAL_PLUS]; minus_pos=self.local_terminals[self.TERMINAL_MINUS]
            painter.setPen(QPen(Qt.black,1)); font_metric=painter.fontMetrics(); char_v_offset=font_metric.ascent()/2
            painter.drawText(plus_pos+QPointF(self.terminal_radius+2,char_v_offset),"+")
            painter.drawText(minus_pos+QPointF(self.terminal_radius+2,char_v_offset),"-")
        if self.isSelected(): pen=QPen(Qt.blue,1,Qt.DashLine); painter.setPen(pen); painter.setBrush(Qt.NoBrush); painter.drawRect(self.boundingRect().adjusted(-2,-2,2,2))
    def rotate_item(self, angle_degrees=90): self.setRotation(self.rotation()+angle_degrees)
    def get_terminal_scene_positions(self): return {tid:self.mapToScene(pos) for tid,pos in self.local_terminals.items()}
    def connect_wire(self, terminal_id, wire_item):
        if terminal_id in self.terminal_connections:
            if wire_item not in self.terminal_connections[terminal_id]: self.terminal_connections[terminal_id].append(wire_item)
    def disconnect_wire(self, terminal_id, wire_item):
        if terminal_id in self.terminal_connections and wire_item in self.terminal_connections[terminal_id]: self.terminal_connections[terminal_id].remove(wire_item)
    def itemChange(self, change, value):
        if change==QGraphicsItem.ItemPositionHasChanged or change==QGraphicsItem.ItemRotationHasChanged:
            if hasattr(self,'terminal_connections'):
                for term_id_key in self.terminal_connections:
                    for wire in self.terminal_connections[term_id_key]:
                        if hasattr(wire,'update_endpoints_from_connections'): wire.update_endpoints_from_connections()
        return super().itemChange(change,value)

class ResistorItem(BaseComponentItem):
    COMPONENT_TYPE = "R"
    def __init__(self, name=None, value="1k", parent=None): super().__init__(name, value, "R", 2, parent); self.local_terminals = { self.TERMINAL_A: QPointF(-self.width/2-self.lead_length,0), self.TERMINAL_B: QPointF(self.width/2+self.lead_length,0) }
    def boundingRect(self): o_w=self.width+2*self.lead_length+2*self.terminal_radius+20; o_h=self.height+2*self.terminal_radius+40; m_d=max(o_w,o_h)*1.2; return QRectF(-m_d/2,-m_d/2,m_d,m_d)
    def paint(self, painter, option, widget=None): painter.setRenderHint(QPainter.Antialiasing); br=QRectF(-self.width/2,-self.height/2,self.width,self.height); p=painter; p.setPen(QPen(Qt.black,2));p.setBrush(QBrush(Qt.white));p.drawRect(br);p.setPen(QPen(Qt.black,2));p.drawLine(QPointF(-self.width/2,0),self.local_terminals[self.TERMINAL_A]);p.drawLine(QPointF(self.width/2,0),self.local_terminals[self.TERMINAL_B]);self.common_paint_logic(p)

class VoltageSourceItem(BaseComponentItem):
    COMPONENT_TYPE = "V"; TERMINAL_PLUS = BaseComponentItem.TERMINAL_A; TERMINAL_MINUS = BaseComponentItem.TERMINAL_B
    def __init__(self, name=None, value="1", source_type="DC", ac_magnitude="1", ac_phase="0", parent=None):
        super().__init__(name, value, "V", 2, parent); self.source_type = source_type; self.ac_magnitude = ac_magnitude; self.ac_phase = ac_phase
        self.radius=20; self.width=self.radius*2; self.height=self.radius*2
        self.local_terminals = { self.TERMINAL_PLUS:QPointF(0,-self.radius-self.lead_length), self.TERMINAL_MINUS:QPointF(0,self.radius+self.lead_length) }
    def set_source_type(self,t): self.source_type=t; self.update(); return True
    def set_ac_magnitude(self,m): self.ac_magnitude=str(m); self.update(); return True
    def set_ac_phase(self,p): self.ac_phase=str(p); self.update(); return True
    def get_spice_value_string(self):
        base_val = self.value
        if self.source_type == "AC":
            try:
                float(self.ac_magnitude); float(self.ac_phase)
                return f"{base_val} AC {self.ac_magnitude} {self.ac_phase}"
            except ValueError:
                return base_val
        return base_val
    def boundingRect(self): o_d=(self.radius+self.lead_length+self.terminal_radius+20)*2; return QRectF(-o_d/2,-o_d/2,o_d,o_d)
    def paint(self, painter, option, widget=None):
        p=painter; p.setRenderHint(QPainter.Antialiasing); cr=QRectF(-self.radius,-self.radius,2*self.radius,2*self.radius)
        p.setPen(QPen(Qt.black,2)); p.setBrush(QBrush(Qt.white)); p.drawEllipse(cr)
        if self.source_type == "AC": path=QPainterPath(); path.moveTo(-self.radius*0.6,0); path.quadTo(-self.radius*0.3,-self.radius*0.5,0,0); path.quadTo(self.radius*0.3,self.radius*0.5,self.radius*0.6,0); p.drawPath(path)
        p.setPen(QPen(Qt.black,2)); p.drawLine(QPointF(0,-self.radius),self.local_terminals[self.TERMINAL_PLUS]); p.drawLine(QPointF(0,self.radius),self.local_terminals[self.TERMINAL_MINUS]); self.common_paint_logic(p,True)

class CapacitorItem(BaseComponentItem):
    COMPONENT_TYPE = "C"
    def __init__(self, name=None, value="1u", parent=None): super().__init__(name,value,"C",2,parent); self.p_s=6; self.p_l=self.height; self.local_terminals = {self.TERMINAL_A:QPointF(-self.p_s/2-self.lead_length,0), self.TERMINAL_B:QPointF(self.p_s/2+self.lead_length,0)}
    def boundingRect(self): o_w=self.p_s+2*self.lead_length+2*self.terminal_radius+self.width+20; o_h=self.p_l+2*self.terminal_radius+40; m_d=max(o_w,o_h)*1.2; return QRectF(-m_d/2,-m_d/2,m_d,m_d)
    def paint(self,p,opt,wid=None): p.setRenderHint(QPainter.Antialiasing);p.setPen(QPen(Qt.black,2));p1x=-self.p_s/2;p2x=self.p_s/2;p.drawLine(self.local_terminals[self.TERMINAL_A],QPointF(p1x,0));p.drawLine(QPointF(p1x,-self.p_l/2),QPointF(p1x,self.p_l/2));p.drawLine(self.local_terminals[self.TERMINAL_B],QPointF(p2x,0));p.drawLine(QPointF(p2x,-self.p_l/2),QPointF(p2x,self.p_l/2));self.common_paint_logic(p)

class InductorItem(BaseComponentItem):
    COMPONENT_TYPE = "L"
    def __init__(self,name=None,value="1mH",parent=None): super().__init__(name,value,"L",2,parent);self.n_l=3;self.l_r=self.height/2;self.local_terminals = {self.TERMINAL_A:QPointF(-self.width/2-self.lead_length,0),self.TERMINAL_B:QPointF(self.width/2+self.lead_length,0)}
    def boundingRect(self): o_w=self.width+2*self.lead_length+2*self.terminal_radius+20;o_h=self.height+2*self.terminal_radius+40;m_d=max(o_w,o_h)*1.2;return QRectF(-m_d/2,-m_d/2,m_d,m_d)
    def paint(self,p,opt,wid=None): p.setRenderHint(QPainter.Antialiasing);p.setPen(QPen(Qt.black,2));p.drawLine(self.local_terminals[self.TERMINAL_A],QPointF(-self.width/2,0));path=QPainterPath();path.moveTo(-self.width/2,0);loop_w=self.width/self.n_l;[path.arcTo(-self.width/2+i*loop_w,-self.l_r,loop_w,2*self.l_r,180.0,-180.0) for i in range(self.n_l)];p.drawPath(path);p.drawLine(QPointF(self.width/2,0),self.local_terminals[self.TERMINAL_B]);self.common_paint_logic(p)

class GroundComponentItem(BaseComponentItem):
    COMPONENT_TYPE = "GND"; TERMINAL_CONNECTION = BaseComponentItem.TERMINAL_A
    def __init__(self,name=None,parent=None): super().__init__(name,"","GND",1,parent);self.width=30;self.height=20;self.local_terminals = {self.TERMINAL_CONNECTION:QPointF(0,-self.height/2)}
    def boundingRect(self): return QRectF(-self.width/2,-self.height/2-5,self.width,self.height+10)
    def paint(self,p,opt,wid=None):
        p.setRenderHint(QPainter.Antialiasing);p.setPen(QPen(Qt.black,2));p1=self.local_terminals[self.TERMINAL_CONNECTION];p2=QPointF(p1.x(),p1.y()+self.height);p.drawLine(p1,p2);
        hack_globals={'line_len_current': self.width * 0.8}
        for i in range(3): p.drawLine(QPointF(p1.x()-hack_globals['line_len_current']/2, p2.y()-i*(self.height/3.5)), QPointF(p1.x()+hack_globals['line_len_current']/2, p2.y()-i*(self.height/3.5))); hack_globals['line_len_current'] *= 0.7
        self.common_paint_logic(p)

class WireItem(QGraphicsItem):
    COMPONENT_TYPE="Wire"
    def __init__(self,s_c=None,e_c=None,p=None):
        super().__init__(p);self.s_c=s_c;self.e_c=e_c
        self.setFlag(QGraphicsItem.ItemIsSelectable);self.setZValue(-1)
        self.p1s=QPointF();self.p2s=QPointF();self.update_endpoints_from_connections()
    def update_endpoints_from_connections(self):
        p1,p2=QPointF(),QPointF()
        def get_tp(conn):
            if conn:
                c,t_id=conn
                if c.scene() and hasattr(c,'local_terminals') and t_id in c.local_terminals: return c.mapToScene(c.local_terminals[t_id])
            return QPointF()
        p1=get_tp(self.s_c); p2=get_tp(self.e_c)
        if self.p1s!=p1 or self.p2s!=p2: self.prepareGeometryChange(); self.p1s=p1; self.p2s=p2; self.update()
    def get_scene_points(self): return self.p1s,self.p2s
    def boundingRect(self): return QRectF(self.mapFromScene(self.p1s),self.mapFromScene(self.p2s)).normalized().adjusted(-5,-5,5,5) if not (self.p1s.isNull() or self.p2s.isNull()) else QRectF()
    def paint(self,p,opt,wid=None):
        if self.p1s.isNull() or self.p2s.isNull(): return
        p.setRenderHint(QPainter.Antialiasing);pen=QPen(Qt.darkCyan,2)
        if self.isSelected(): pen.setColor(Qt.blue); pen.setStyle(Qt.DashLine)
        p.setPen(pen);p.drawLine(self.mapFromScene(self.p1s),self.mapFromScene(self.p2s))
    def cleanup_connections(self):
        def dc(conn):
            if conn: c,t_id=conn; c.disconnect_wire(t_id,self) if hasattr(c,'disconnect_wire') else None
        dc(self.s_c); dc(self.e_c); self.s_c=None; self.e_c=None

class SchematicView(QGraphicsView):
    def __init__(self,s,p=None):super().__init__(s,p);self.setAcceptDrops(True);self.c_t=None;self.w_s_c=None;self.t_l=None;self.s_c_e=None
    def set_tool(self,t_n): self.c_t=t_n;self.w_s_c=None;self.s_c_e=None; (self.scene().removeItem(self.t_l) if self.t_l and self.t_l.scene() else None) ;self.t_l=None;self.setCursor(Qt.CrossCursor if t_n=="Wire" else Qt.ArrowCursor)
    def _get_snapped_connection(self,s_p_c):
        for itm in self.scene().items():
            if isinstance(itm,BaseComponentItem) and itm.COMPONENT_TYPE!="Wire": # Check against string "Wire"
                if hasattr(itm,'get_terminal_scene_positions') and hasattr(itm,'snap_radius'):
                    for t_id,t_s_p in itm.get_terminal_scene_positions().items():
                        if (t_s_p-s_p_c).manhattanLength()<itm.snap_radius*2: return itm,t_id,t_s_p
        return None
    def dropEvent(self,e):
        if e.mimeData().hasFormat("application/x-componentname"):
            cn=e.mimeData().data("application/x-componentname").data().decode('utf-8')
            if cn=="Wire": e.ignore();return # "Wire" is a tool, not a component to drop
            dp=self.mapToScene(e.pos());itm=None
            # Use COMPONENT_TYPE attributes for comparison
            if cn==ResistorItem.COMPONENT_TYPE: itm=ResistorItem()
            elif cn==VoltageSourceItem.COMPONENT_TYPE: itm=VoltageSourceItem()
            elif cn==CapacitorItem.COMPONENT_TYPE: itm=CapacitorItem()
            elif cn==InductorItem.COMPONENT_TYPE: itm=InductorItem()
            elif cn==GroundComponentItem.COMPONENT_TYPE: itm=GroundComponentItem()
            if itm: itm.setPos(dp);self.scene().addItem(itm); e.acceptProposedAction()
            else: e.ignore()
        else:super().dropEvent(e)
        self.set_tool(None)
    def mousePressEvent(self,e):
        sp=self.mapToScene(e.pos())
        if self.c_t=="Wire":
            if e.button()==Qt.LeftButton:
                sd=self._get_snapped_connection(sp)
                if self.w_s_c is None:
                    if sd: self.w_s_c=(sd[0],sd[1]); sdp=sd[2]; self.t_l=self.scene().addLine(QLineF(sdp,sdp),QPen(Qt.darkGray,1,Qt.DashLine))
                else:
                    ecd=self.s_c_e or (sd if sd else None)
                    if ecd and self.w_s_c and not (ecd[0]==self.w_s_c[0] and ecd[1]==self.w_s_c[1]):
                        w=WireItem(self.w_s_c,ecd); self.scene().addItem(w);sc,st_id=self.w_s_c; ec,et_id=ecd
                        if hasattr(sc,'connect_wire'):sc.connect_wire(st_id,w)
                        if hasattr(ec,'connect_wire'):ec.connect_wire(et_id,w)
                    self.w_s_c=None; self.s_c_e=None; (self.scene().removeItem(self.t_l) if self.t_l and self.t_l.scene() else None); self.t_l=None
            elif e.button()==Qt.RightButton: self.w_s_c=None;self.s_c_e=None; self.set_tool(None); (self.scene().removeItem(self.t_l) if self.t_l and self.t_l.scene() else None); self.t_l=None
        else:super().mousePressEvent(e)
    def mouseMoveEvent(self,e):
        sp=self.mapToScene(e.pos())
        if self.c_t=="Wire" and self.w_s_c:
            sd=self._get_snapped_connection(sp); sc,st_id=self.w_s_c
            if not sc.scene() or not hasattr(sc,'local_terminals') or st_id not in sc.local_terminals: self.w_s_c=None;self.s_c_e=None; (self.scene().removeItem(self.t_l) if self.t_l and self.t_l.scene() else None);self.t_l=None;self.set_tool(None);return
            sdp=sc.mapToScene(sc.local_terminals[st_id])
            line_pen = QPen(Qt.darkGray,1,Qt.DashLine)
            if sd: self.s_c_e=(sd[0],sd[1]); dep=sd[2]; line_pen.setColor(Qt.green); line_pen.setStyle(Qt.SolidLine); line_pen.setWidth(2)
            else: self.s_c_e=None; dep=sp
            if self.t_l: self.t_l.setPen(line_pen); self.t_l.setLine(QLineF(sdp,dep))
        else:super().mouseMoveEvent(e)
    def contextMenuEvent(self, event):
        item_at_view_pos = self.itemAt(event.pos())
        if isinstance(item_at_view_pos, BaseComponentItem) and item_at_view_pos.COMPONENT_TYPE != "Wire": # Check against string "Wire"
            menu = QMenu(self); rotate_action = menu.addAction("Rotate"); delete_action = menu.addAction("Delete"); action = menu.exec_(event.globalPos())
            if action == rotate_action and hasattr(item_at_view_pos, 'rotate_item'): item_at_view_pos.rotate_item(90)
            elif action == delete_action: self._delete_item_and_connections(item_at_view_pos)
        else: super().contextMenuEvent(event)
    def _delete_item_and_connections(self, item_to_delete):
        if not item_to_delete or not item_to_delete.scene(): return
        if isinstance(item_to_delete, WireItem): item_to_delete.cleanup_connections()
        elif isinstance(item_to_delete, BaseComponentItem):
            for term_id_key in list(item_to_delete.terminal_connections.keys()): # list() for safe iteration
                for wire in list(item_to_delete.terminal_connections[term_id_key]):
                    wire.cleanup_connections(); (self.scene().removeItem(wire) if wire.scene() else None)
        self.scene().removeItem(item_to_delete)
    def keyPressEvent(self,e):
        si=self.scene().selectedItems()
        if e.key()==Qt.Key_R: [itm.rotate_item(90) for itm in si if hasattr(itm,'rotate_item')] if si else super().keyPressEvent(e)
        elif e.key()==Qt.Key_Delete or e.key()==Qt.Key_Backspace: [self._delete_item_and_connections(itm) for itm in list(si)] if si else super().keyPressEvent(e)
        elif e.key()==Qt.Key_Escape:
            if self.c_t=="Wire": self.w_s_c=None;self.s_c_e=None; (self.scene().removeItem(self.t_l) if self.t_l and self.t_l.scene() else None); self.t_l=None
            self.set_tool(None)
        else:super().keyPressEvent(e)
    def dragEnterEvent(self,e): cn=e.mimeData().data("application/x-componentname").data().decode('utf-8') if e.mimeData().hasFormat("application/x-componentname") else None; (self.set_tool(None) or e.acceptProposedAction()) if cn and cn!="Wire" else (e.ignore() if cn=="Wire" else super().dragEnterEvent(e))
    def dragMoveEvent(self,e): e.acceptProposedAction() if e.mimeData().hasFormat("application/x-componentname") else super().dragMoveEvent(e)

class ComponentListWidget(QListWidget):
    def __init__(self,p=None):
        super().__init__(p); self.setDragEnabled(True)
        self.addItems([ResistorItem.COMPONENT_TYPE, VoltageSourceItem.COMPONENT_TYPE, CapacitorItem.COMPONENT_TYPE, InductorItem.COMPONENT_TYPE, GroundComponentItem.COMPONENT_TYPE, "Wire"])
        self.itemClicked.connect(self.on_item_clicked); self.parent_view=None
    def on_item_clicked(self,itm): self.parent_view.set_tool("Wire") if self.parent_view and itm.text()=="Wire" else None
    def startDrag(self,sa):
        itm=self.currentItem()
        if itm and itm.text()!="Wire":
            md=QMimeData(); md.setData("application/x-componentname",itm.text().encode('utf-8'))
            d=QDrag(self); d.setMimeData(md); d.exec_(sa)

class PropertiesWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.layout=QFormLayout(self); self.current_item=None
        self.name_edit=QLineEdit(); self.layout.addRow("Name:",self.name_edit)
        self.value_label=QLabel("Value (DC):"); self.value_edit=QLineEdit(); self.layout.addRow(self.value_label,self.value_edit)
        self.source_type_combo=QComboBox(); self.source_type_combo.addItems(["DC","AC"])
        self.ac_mag_edit=QLineEdit(); self.ac_phase_edit=QLineEdit("0")

        self.vs_specific_widgets_with_labels = [
            (QLabel("Source Type:"), self.source_type_combo),
            (QLabel("AC Magnitude:"), self.ac_mag_edit),
            (QLabel("AC Phase (deg):"), self.ac_phase_edit)
        ]
        for label, widget in self.vs_specific_widgets_with_labels: self.layout.addRow(label, widget)

        self.name_edit.editingFinished.connect(self.on_name_changed); self.value_edit.editingFinished.connect(self.on_value_changed)
        self.source_type_combo.currentIndexChanged.connect(self.on_source_type_changed)
        self.ac_mag_edit.editingFinished.connect(self.on_ac_mag_changed); self.ac_phase_edit.editingFinished.connect(self.on_ac_phase_changed)
        self.clear_properties()

    def set_vs_specific_rows_visible(self, visible):
        for label, widget in self.vs_specific_widgets_with_labels:
            widget.setVisible(visible)
            if label: label.setVisible(visible)

    def display_properties(self,item):
        self.current_item=item; is_vs=isinstance(item,VoltageSourceItem); is_gnd=(hasattr(item,'COMPONENT_TYPE') and item.COMPONENT_TYPE=="GND")
        self.set_vs_specific_rows_visible(is_vs)
        if isinstance(item,BaseComponentItem) and item.COMPONENT_TYPE!="Wire":
            self.name_edit.setText(item.name); self.name_edit.setEnabled(True);self.value_label.setText("DC Value/Offset:" if is_vs else "Value:")
            if is_gnd: self.value_edit.setText("");self.value_edit.setEnabled(False)
            else: self.value_edit.setText(item.value);self.value_edit.setEnabled(True)
            if is_vs: self.source_type_combo.setCurrentIndex(self.source_type_combo.findText(item.source_type));self.ac_mag_edit.setText(item.ac_magnitude);self.ac_phase_edit.setText(item.ac_phase);self.on_source_type_changed()
        else: self.clear_properties()
    def clear_properties(self):
        self.current_item=None;self.name_edit.setText("");self.value_edit.setText("");self.name_edit.setEnabled(False);self.value_edit.setEnabled(False);self.value_label.setText("Value:")
        self.set_vs_specific_rows_visible(False)
        self.source_type_combo.setCurrentIndex(0);self.ac_mag_edit.setText("");self.ac_phase_edit.setText("0")
    def on_name_changed(self):
        if self.current_item and hasattr(self.current_item,'set_name'):
            if not self.current_item.set_name(self.name_edit.text()): self.name_edit.setText(self.current_item.name)
    def _validate_and_set_value(self, line_edit, item_setter_method_name, original_value_getter_name, is_numeric_only=False, allow_symbolic_non_numeric=True):
        if not self.current_item or not hasattr(self.current_item, item_setter_method_name): return
        new_text = line_edit.text().strip()
        original_value = str(getattr(self.current_item, original_value_getter_name))
        parsed_val = parse_value_with_si_suffix(new_text); valid_input = False; value_to_set = new_text
        if isinstance(parsed_val, (float, int)):
            valid_input=True; value_to_set=str(parsed_val)
            if is_numeric_only and not new_text.replace('.', '', 1).replace('-', '', 1).isdigit():
                 is_parsable_to_num_by_suffix_parser = not isinstance(parse_value_with_si_suffix(new_text), str)
                 if not is_parsable_to_num_by_suffix_parser:
                      valid_input = False
        elif not is_numeric_only and allow_symbolic_non_numeric and isinstance(parsed_val, str) and re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$",parsed_val):
            valid_input=True
        elif is_numeric_only and not isinstance(parsed_val, (float, int)):
            valid_input=False

        if valid_input:
            setter_method = getattr(self.current_item, item_setter_method_name)
            if not setter_method(value_to_set): line_edit.setText(original_value)
        else:
            QMessageBox.warning(self,"Invalid Input",f"Value '{new_text}' is not valid for this field.")
            line_edit.setText(original_value)
    def on_value_changed(self):
        if self.current_item and hasattr(self.current_item,'value') and self.current_item.COMPONENT_TYPE!="GND":
            self._validate_and_set_value(self.value_edit, "set_value", "value", allow_symbolic_non_numeric=True)
    def on_source_type_changed(self, index=None):
        if self.current_item and isinstance(self.current_item,VoltageSourceItem):
            st=self.source_type_combo.currentText(); self.current_item.set_source_type(st); is_ac=(st=="AC")
            for label, widget in self.vs_specific_widgets_with_labels:
                if widget == self.ac_mag_edit or widget == self.ac_phase_edit or \
                   (label and (label.text() == "AC Magnitude:" or label.text() == "AC Phase (deg):")):
                    widget.setVisible(is_ac)
                    if label: label.setVisible(is_ac)
            self.value_label.setText("DC Value/Offset:" if is_ac else "DC Value:")
    def on_ac_mag_changed(self):
        if self.current_item and isinstance(self.current_item,VoltageSourceItem):
            self._validate_and_set_value(self.ac_mag_edit, "set_ac_magnitude", "ac_magnitude", allow_symbolic_non_numeric=True)
    def on_ac_phase_changed(self):
        if self.current_item and isinstance(self.current_item,VoltageSourceItem):
            self._validate_and_set_value(self.ac_phase_edit, "set_ac_phase", "ac_phase", is_numeric_only=True)

class ACAnalysisDialog(QDialog):
    def __init__(self,p=None,curr_p=None):super().__init__(p);self.setWindowTitle("AC Analysis");layout=QFormLayout(self);self.stc=QComboBox();self.stc.addItems(["DEC","LIN","OCT"]);self.pe=QLineEdit("10");self.fse=QLineEdit("1");self.fspe=QLineEdit("1M");layout.addRow("Sweep:",self.stc);layout.addRow("Pts:",self.pe);layout.addRow("Fstart:",self.fse);layout.addRow("Fstop:",self.fspe);self.btns=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);self.btns.accepted.connect(self.accept);self.btns.rejected.connect(self.reject);layout.addWidget(self.btns);self.populate(curr_p) if curr_p else None
    def populate(self,p):self.stc.setCurrentText(p.get('type','DEC'));self.pe.setText(p.get('points','10'));self.fse.setText(p.get('fstart','1'));self.fspe.setText(p.get('fstop','1M'))
    def get_params(self):return{'type':self.stc.currentText(),'points':self.pe.text(),'fstart':self.fse.text(),'fstop':self.fspe.text()}

class SchematicEditor(QMainWindow):
    FAVORITES_DIR="circuits/favorites"
    def __init__(self):
        super().__init__()
        self.current_filename=None; self.temp_files_to_cleanup=[]; self.ac_analysis_params=None; self.parsed_measure_results={}
        os.makedirs(self.FAVORITES_DIR,exist_ok=True)
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Symbolic Circuit Schematic Editor');self.setGeometry(100,100,1600,900)
        self.scene=QGraphicsScene(self);self.scene.setSceneRect(-400,-300,800,600);self.scene.selectionChanged.connect(self.on_scene_selection_changed)
        self.schematic_view=SchematicView(self.scene,self);self.schematic_view.setFrameShape(QFrame.StyledPanel);self.schematic_view.setRenderHint(QPainter.Antialiasing);self.setCentralWidget(self.schematic_view)
        components_dock=QDockWidget("Components",self);self.cl=ComponentListWidget();self.cl.parent_view=self.schematic_view;components_dock.setWidget(self.cl);self.addDockWidget(Qt.LeftDockWidgetArea,components_dock)
        properties_dock=QDockWidget("Properties",self);self.pw=PropertiesWidget();properties_dock.setWidget(self.pw);self.addDockWidget(Qt.RightDockWidgetArea,properties_dock);self.pw.clear_properties()
        self.output_tabs=QTabWidget();self.solver_log_output_area=QTextEdit();self.solver_log_output_area.setReadOnly(True);self.solver_log_output_area.setFont(QFont("Monospace",9));self.output_tabs.addTab(self.solver_log_output_area,"Solver Log & Raw Output")
        self.measured_results_table=QTableWidget();self.measured_results_table.setColumnCount(3);self.measured_results_table.setHorizontalHeaderLabels(["Measurement Name","Expression","Result Value"]);self.measured_results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);self.measured_results_table.setEditTriggers(QTableWidget.NoEditTriggers);self.output_tabs.addTab(self.measured_results_table,"Measured Results")
        self.plots_tab_widget_container=QWidget();self.plots_layout=QVBoxLayout(self.plots_tab_widget_container);self.plots_scroll_area=QScrollArea();self.plots_scroll_area.setWidgetResizable(True);self.plots_scroll_area.setWidget(self.plots_tab_widget_container);self.output_tabs.addTab(self.plots_scroll_area,"Plots")
        self.solution_path_area=QTextEdit();self.solution_path_area.setReadOnly(True);self.solution_path_area.setFont(QFont("Monospace",9));self.output_tabs.addTab(self.solution_path_area,"Solution Path / Analysis Steps")
        output_dock=QDockWidget("Output",self);output_dock.setWidget(self.output_tabs);self.addDockWidget(Qt.BottomDockWidgetArea,output_dock)
        menubar=self.menuBar();file_menu=menubar.addMenu('&File')
        actions = [('&Open Circuit...','Ctrl+O',"Open a circuit from a JSON file",self.open_circuit),('&Save Circuit','Ctrl+S',"Save the current circuit",self.save_circuit),('Save Circuit &As...','Ctrl+Shift+S',"Save the current circuit to a new file",self.save_circuit_as),(None),('Add to &Favorites...','',"Save current circuit to favorites",self.add_to_favorites),('Open &Favorite...','',"Open a circuit from favorites",self.open_favorite),(None),('&Exit','Ctrl+Q',"Exit the application",self.close)]
        for item in actions:
            if item is None: file_menu.addSeparator(); continue
            text, shortcut, tip, callback = item; action = QAction(text, self); action.setShortcut(shortcut) if shortcut else None; action.setToolTip(tip) if tip else None; action.triggered.connect(callback); file_menu.addAction(action)
        circuit_menu = menubar.addMenu('&Circuit');run_sim_action = QAction('&Run Simulation', self); run_sim_action.setToolTip("Generate netlist and run simulation"); run_sim_action.triggered.connect(self.run_simulation); circuit_menu.addAction(run_sim_action);set_ac_action = QAction('Set &AC Analysis...', self); set_ac_action.setToolTip("Configure AC analysis parameters"); set_ac_action.triggered.connect(self.set_ac_analysis_dialog); circuit_menu.addAction(set_ac_action)
        self.statusBar().showMessage('Ready.')

    def set_ac_analysis_dialog(self):dialog=ACAnalysisDialog(self,self.ac_analysis_params);(setattr(self,'ac_analysis_params',dialog.get_params()),self.statusBar().showMessage(f"AC Set: {self.ac_analysis_params['type']} {self.ac_analysis_params['points']}, {self.ac_analysis_params['fstart']}-{self.ac_analysis_params['fstop']}",3000)) if dialog.exec_()==QDialog.Accepted else self.statusBar().showMessage("AC setup cancelled.",2000)
    def _clear_plots_tab(self):[ (c.widget().deleteLater() if c.widget() else None) for c in [self.plots_layout.takeAt(0) for _ in range(self.plots_layout.count())] ]

    def _parse_and_display_measure_results(self,rsc):
        self.measured_results_table.setRowCount(0);self.parsed_measure_results.clear()
        pattern=re.compile(r"^(?P<name>\S+?):\s*(?P<expr>v\([\w\.\-\+]+\)|i\([\w\.\-\+]+\)|isub\([\w\.\-\+]+\)|[\w\.\-\+]+)\s*=\s*---------------------\s*(?P<value>.+?)(?=(?:\r?\n){2}\S+?:|\Z)",re.MULTILINE|re.DOTALL)
        mf=0
        for m in pattern.finditer(rsc):
            mf+=1;d=m.groupdict();n=d['name'].strip();es=d['expr'].strip();vs=d['value'].strip().replace("\n"," ")
            r=self.measured_results_table.rowCount();self.measured_results_table.insertRow(r)
            self.measured_results_table.setItem(r,0,QTableWidgetItem(n));self.measured_results_table.setItem(r,1,QTableWidgetItem(es));self.measured_results_table.setItem(r,2,QTableWidgetItem(vs))
            if (es.startswith("v(") or es.startswith("i(")) and es.endswith(")"): self.parsed_measure_results[es] = vs
        if mf==0:self.measured_results_table.insertRow(0);self.measured_results_table.setItem(0,0,QTableWidgetItem("No .measure results found in output."));self.measured_results_table.setSpan(0,0,1,3)

    def _generate_spice_netlist_string(self,netlist_component_data, final_node_names_for_comps_tuple_keys, all_unique_node_names):
        spice_lines=["* Auto-generated SPICE netlist from GUI"]
        components_in_netlist = []
        for comp_data in netlist_component_data:
            comp_type = comp_data['type']; comp_name = comp_data['name']; node_list = comp_data['nodes']; value_str = comp_data['value']
            if comp_type == "GND": continue
            spice_lines.append(f"{comp_name} {' '.join(node_list)} {value_str}"); components_in_netlist.append(comp_name)
            safe_comp_name_for_measure = re.sub(r'[^a-zA-Z0-9_]', '_', comp_name)
            analysis_type = "ac" if self.ac_analysis_params else "dc"
            if len(node_list) == 2 :
                 spice_lines.append(f".measure {analysis_type} I_{safe_comp_name_for_measure} i({comp_name})")

        if not components_in_netlist: spice_lines.append("* Empty circuit (or only ground symbols).")
        else:
            for node_name in sorted(list(all_unique_node_names)):
                safe_node_name_for_measure = re.sub(r'[^a-zA-Z0-9_]', '_', node_name)
                analysis_type = "ac" if self.ac_analysis_params else "dc"
                spice_lines.append(f".measure {analysis_type} V_{safe_node_name_for_measure} v({node_name})")
        if self.ac_analysis_params:
            ac = self.ac_analysis_params
            try: float(ac['points']); float(parse_value_with_si_suffix(ac['fstart'])); float(parse_value_with_si_suffix(ac['fstop']))
            except (ValueError, KeyError) as e: self.solver_log_output_area.append(f"Warning: Invalid AC parameters ({e}). .ac line not added.\n")
            else: spice_lines.append(f".ac {ac['type']} {ac['points']} {ac['fstart']} {ac['fstop']}")
        return "\n".join(spice_lines)

    def run_simulation(self):
        self.solver_log_output_area.clear();self.measured_results_table.setRowCount(0);self._clear_plots_tab();self.solution_path_area.clear();self.parsed_measure_results.clear()
        all_scene_items = self.scene.items()
        components_on_scene = [item for item in all_scene_items if isinstance(item, BaseComponentItem) and item.COMPONENT_TYPE != "Wire"]
        wires_on_scene = [item for item in all_scene_items if isinstance(item, WireItem)]
        if not components_on_scene: self.solver_log_output_area.setText("No components in the schematic to simulate."); return

        dsu_parent = {};
        def dsu_find(item_term_tuple):
            if item_term_tuple not in dsu_parent: dsu_parent[item_term_tuple] = item_term_tuple; return item_term_tuple
            if dsu_parent[item_term_tuple] == item_term_tuple: return item_term_tuple
            dsu_parent[item_term_tuple] = dsu_find(dsu_parent[item_term_tuple]); return dsu_parent[item_term_tuple]
        def dsu_union(t1,t2): r1=dsu_find(t1); r2=dsu_find(t2); dsu_parent[r2]=r1 if r1!=r2 else None

        all_component_terminals = []; ground_terminal_reps = set()
        for comp in components_on_scene:
            if hasattr(comp, 'local_terminals'):
                for term_id in comp.local_terminals.keys():
                    terminal_tuple = (comp, term_id); all_component_terminals.append(terminal_tuple); dsu_find(terminal_tuple)
                    if comp.COMPONENT_TYPE == "GND": ground_terminal_reps.add(dsu_find(terminal_tuple))
        for wire in wires_on_scene:
            if wire.s_c and wire.e_c: dsu_find(wire.s_c); dsu_find(wire.e_c); dsu_union(wire.s_c, wire.e_c)
        if len(ground_terminal_reps) > 1:
            first_ground_rep = list(ground_terminal_reps)[0]
            for other_ground_rep in list(ground_terminal_reps)[1:]: dsu_union(first_ground_rep, other_ground_rep)
            if first_ground_rep: ground_terminal_reps = {dsu_find(first_ground_rep)}

        node_rep_to_name_map = {}; next_node_idx = 1
        unified_ground_rep = list(ground_terminal_reps)[0] if ground_terminal_reps else None
        if unified_ground_rep: node_rep_to_name_map[unified_ground_rep] = "0"
        sorted_unique_reps = sorted(list(set(dsu_find(ct) for ct in all_component_terminals)), key=lambda x_rep: (x_rep != unified_ground_rep, id(x_rep[0]), x_rep[1]))
        for rep in sorted_unique_reps:
            if rep not in node_rep_to_name_map:
                if not unified_ground_rep and "0" not in node_rep_to_name_map.values(): node_rep_to_name_map[rep] = "0"; unified_ground_rep = rep
                else: node_rep_to_name_map[rep] = f"n{next_node_idx}"; next_node_idx +=1

        all_unique_node_names = set(node_rep_to_name_map.values())
        final_node_names_for_comps_tuple_keys = {}
        netlist_component_data = []
        for comp in components_on_scene:
            if hasattr(comp, 'local_terminals') and comp.COMPONENT_TYPE != "Wire":
                comp_nodes_for_spice = []
                term_ids_ordered = sorted(list(comp.local_terminals.keys()))
                if comp.COMPONENT_TYPE == "V": term_ids_ordered = [comp.TERMINAL_PLUS, comp.TERMINAL_MINUS]
                for term_id in term_ids_ordered:
                    if term_id not in comp.local_terminals: continue
                    representative = dsu_find((comp,term_id)); node_name = node_rep_to_name_map.get(representative, f"unmapped_{comp.name}_t{term_id}")
                    comp_nodes_for_spice.append(node_name); final_node_names_for_comps_tuple_keys[(comp, term_id)] = node_name
                if comp.COMPONENT_TYPE != "GND":
                    netlist_component_data.append({'type': comp.COMPONENT_TYPE, 'name': comp.name, 'nodes': comp_nodes_for_spice, 'value': comp.get_spice_value_string() if hasattr(comp, 'get_spice_value_string') else comp.value})

        spice_netlist_str = self._generate_spice_netlist_string(netlist_component_data, final_node_names_for_comps_tuple_keys, all_unique_node_names)
        self.solution_path_area.append("Generated SPICE Netlist:\n" + spice_netlist_str)
        self.solver_log_output_area.append("SPICE Netlist:\n" + spice_netlist_str + "\n" + "-"*20 + "\n")

        temp_spice_filepath=None; temp_results_base_filepath_stem=None; temp_dir = tempfile.gettempdir()
        try:
            fd, temp_spice_filepath = tempfile.mkstemp(suffix='.sp', prefix='gui_sim_', text=True, dir=temp_dir)
            with os.fdopen(fd, 'w') as tmp_sp_file: tmp_sp_file.write(spice_netlist_str)
            self.temp_files_to_cleanup.append(temp_spice_filepath)
            temp_results_base_filepath_stem = os.path.join(temp_dir, os.path.splitext(os.path.basename(temp_spice_filepath))[0])
            script_dir = os.path.dirname(os.path.abspath(__file__)); scs_script_path = os.path.join(script_dir, "scs.py")
            command = ["python", scs_script_path, "-i", temp_spice_filepath, "-o", temp_results_base_filepath_stem]
            self.solver_log_output_area.append(f"Executing: {' '.join(command)}\n")
            process = subprocess.run(command, capture_output=True, text=True, cwd=script_dir, timeout=30)
            self.solver_log_output_area.append("scs.py STDOUT:\n" + (process.stdout or "N/A") + "\n")
            self.solver_log_output_area.append("scs.py STDERR:\n" + (process.stderr or "N/A") + "\n")
            results_filepath = temp_results_base_filepath_stem + ".results"; log_filepath = temp_results_base_filepath_stem + ".log"
            self.temp_files_to_cleanup.extend([results_filepath, log_filepath])

            if process.returncode == 0:
                self.statusBar().showMessage("Simulation successful.", 5000)
                if os.path.exists(results_filepath):
                    with open(results_filepath, 'r') as f_res: results_content = f_res.read()
                    self.solver_log_output_area.append("\n--- Raw Results ---\n" + results_content)
                    self._parse_and_display_measure_results(results_content)
                    self.solution_path_area.append("\n\n--- Component Voltage/Current Analysis ---")
                    s_sym = sympy.symbols('s')

                    for comp_item_analysis in components_on_scene:
                        if comp_item_analysis.COMPONENT_TYPE == "GND": continue
                        comp_text_report = f"{comp_item_analysis.COMPONENT_TYPE} {comp_item_analysis.name}({comp_item_analysis.value}): "
                        try:
                            if comp_item_analysis.COMPONENT_TYPE == "R":
                                n1_name = final_node_names_for_comps_tuple_keys.get((comp_item_analysis, comp_item_analysis.TERMINAL_A))
                                n2_name = final_node_names_for_comps_tuple_keys.get((comp_item_analysis, comp_item_analysis.TERMINAL_B))
                                v1_str = self.parsed_measure_results.get(f"v({n1_name})"); v2_str = self.parsed_measure_results.get(f"v({n2_name})")
                                if v1_str and v2_str:
                                    v1_expr=sympy.sympify(v1_str,locals={'s':s_sym}); v2_expr=sympy.sympify(v2_str,locals={'s':s_sym})
                                    vd_expr = sympy.simplify(v1_expr-v2_expr)
                                    r_val = parse_value_with_si_suffix(comp_item_analysis.value)
                                    r_sym_expr = sympy.sympify(r_val, locals={'s':s_sym}) if isinstance(r_val,(int,float)) else sympy.symbols(comp_item_analysis.value)
                                    i_calc_expr = sympy.simplify(vd_expr / r_sym_expr)
                                    comp_text_report += f"V_drop = {vd_expr}, I_calculated = {i_calc_expr}"
                                else: comp_text_report += "Missing node voltage(s) for full analysis."
                            elif comp_item_analysis.COMPONENT_TYPE == "C" and self.ac_analysis_params:
                                c_val = parse_value_with_si_suffix(comp_item_analysis.value)
                                if isinstance(c_val,(int,float)): Zc = sympy.simplify(1/(s_sym*sympy.sympify(c_val,locals={'s':s_sym}))); comp_text_report += f"Zc = {Zc}"
                                else: comp_text_report += f"Zc = 1/(s*{comp_item_analysis.value})"
                            elif comp_item_analysis.COMPONENT_TYPE == "L" and self.ac_analysis_params:
                                l_val = parse_value_with_si_suffix(comp_item_analysis.value)
                                if isinstance(l_val,(int,float)): Zl = sympy.simplify(s_sym*sympy.sympify(l_val,locals={'s':s_sym})); comp_text_report += f"Zl = {Zl}"
                                else: comp_text_report += f"Zl = s*{comp_item_analysis.value}"

                            measured_i_str = self.parsed_measure_results.get(f"i({comp_item_analysis.name})")
                            if measured_i_str: comp_text_report += f", I_measured = {measured_i_str}"
                            self.solution_path_area.append(comp_text_report)
                        except Exception as e_comp_an: self.solution_path_area.append(f"{comp_text_report} Analysis Error: {e_comp_an}")

                    # --- KCL Display ---
                    self.solution_path_area.append("\n--- KCL Equations (Sum of currents at node = 0) ---")

                    for node_name_kcl in sorted(list(all_unique_node_names)):
                        kcl_current_symbols_list = []
                        current_definitions_for_node = []

                        for comp_kcl in components_on_scene:
                            if comp_kcl.COMPONENT_TYPE == "GND": continue

                            comp_current_expr_str = self.parsed_measure_results.get(f"i({comp_kcl.name})")

                            current_symbol_name_for_kcl = f"I_{comp_kcl.name.replace('.','_').replace('-','neg').replace(':','_')}"
                            current_sympy_symbol = sympy.symbols(current_symbol_name_for_kcl)

                            term_a_node = final_node_names_for_comps_tuple_keys.get((comp_kcl, comp_kcl.TERMINAL_A))
                            term_b_node = final_node_names_for_comps_tuple_keys.get((comp_kcl, comp_kcl.TERMINAL_B)) if hasattr(comp_kcl, 'TERMINAL_B') else None

                            sign = 0
                            if term_a_node == node_name_kcl: sign = 1
                            elif term_b_node == node_name_kcl: sign = -1

                            if sign != 0:
                                kcl_current_symbols_list.append(sign * current_sympy_symbol)
                                if comp_current_expr_str:
                                    current_definitions_for_node.append(f"  {current_sympy_symbol} = {comp_current_expr_str}")
                                else:
                                    # Only add to definitions if current was expected (i.e., it's a 2-terminal component)
                                    if hasattr(comp_kcl, 'TERMINAL_B'): # Simple check for 2-terminal
                                        current_definitions_for_node.append(f"  {current_sympy_symbol} (definition not found for i({comp_kcl.name}))")

                        if kcl_current_symbols_list:
                            kcl_equation_sym = sympy.Add(*kcl_current_symbols_list, evaluate=False)
                            try:
                                simplified_kcl_eq = sympy.simplify(kcl_equation_sym)
                                self.solution_path_area.append(f"Node {node_name_kcl}: {simplified_kcl_eq} = 0")
                            except Exception as e_simplify:
                                self.solution_path_area.append(f"Node {node_name_kcl}: {kcl_equation_sym} = 0  (Simplification error: {e_simplify})")

                            if current_definitions_for_node:
                                self.solution_path_area.append("  where:")
                                for definition in current_definitions_for_node: self.solution_path_area.append(f"    {definition}")
                            self.solution_path_area.append("")
                        # else: self.solution_path_area.append(f"Node {node_name_kcl}: (No component currents determined for this node or isolated node)\n")

                else: self.solver_log_output_area.append(f"\nERROR: Results file '{results_filepath}' not found.")
                plot_files = glob.glob(temp_results_base_filepath_stem + "_*.png")
                self._clear_plots_tab()
                if plot_files:
                    for plot_file_path in sorted(plot_files):
                        pixmap = QPixmap(plot_file_path)
                        if not pixmap.isNull(): plot_label = QLabel(); plot_label.setPixmap(pixmap.scaledToWidth(self.plots_scroll_area.width() - 30, Qt.SmoothTransformation)); self.plots_layout.addWidget(plot_label); self.temp_files_to_cleanup.append(plot_file_path)
                        else: self.plots_layout.addWidget(QLabel(f"Could not load plot: {os.path.basename(plot_file_path)}"))
                    if self.sender() and hasattr(self.sender(), 'text') and self.sender().text() == '&Run Simulation': self.output_tabs.setCurrentWidget(self.plots_scroll_area)
                else: self.plots_layout.addWidget(QLabel("No plots were generated."))
            else:
                self.statusBar().showMessage(f"Simulation failed (code: {process.returncode}). See log.", 5000)
                if os.path.exists(log_filepath):
                    with open(log_filepath, 'r') as f_log: self.solver_log_output_area.append("\n--- Solver Log (on error) ---\n" + f_log.read())
        except FileNotFoundError as e_fnf: QMessageBox.critical(self, "Simulation Error", f"scs.py not found. Ensure it is in the same directory or PATH.\nError: {e_fnf}"); self.solver_log_output_area.append(f"ERROR: scs.py not found. {e_fnf}")
        except subprocess.TimeoutExpired: QMessageBox.warning(self, "Simulation Timeout", "scs.py took too long (30s)."); self.solver_log_output_area.append("ERROR: Simulation process timed out.")
        except Exception as e_sim: QMessageBox.critical(self, "Simulation Error", f"An unexpected error occurred: {e_sim}"); self.solver_log_output_area.append(f"PYTHON ERROR during simulation: {type(e_sim).__name__}: {e_sim}")

    def on_scene_selection_changed(self):si=self.scene.selectedItems();self.pw.display_properties(si[0]) if len(si)==1 and isinstance(si[0],BaseComponentItem) and si[0].COMPONENT_TYPE!="Wire" else self.pw.clear_properties()
    def save_circuit_as(self):fn,_=QFileDialog.getSaveFileName(self,"Save As",self.current_filename or os.path.join(os.getcwd(),"untitled.json"),"*.json");(setattr(self,'current_filename',fn),self.save_circuit_to_file(fn),self.setWindowTitle(f"Schematic Editor - {os.path.basename(fn)}")) if fn else self.statusBar().showMessage("Save cancelled.",2000)
    def save_circuit(self):self.save_circuit_to_file(self.current_filename) if self.current_filename else self.save_circuit_as()
    def save_circuit_to_file(self,fn):
        if not fn: return
        d={'components':[],'wires':[]}
        for i in self.scene.items():
            if isinstance(i,BaseComponentItem) and i.COMPONENT_TYPE!="Wire": d['components'].append({'type':i.COMPONENT_TYPE,'name':i.name,'value':(i.value if i.COMPONENT_TYPE!="GND" else ""),**(({'source_type':i.source_type,'ac_magnitude':i.ac_magnitude,'ac_phase':i.ac_phase} if isinstance(i,VoltageSourceItem) else {})),'pos_x':i.pos().x(),'pos_y':i.pos().y(),'rotation':i.rotation()})
            elif isinstance(i,WireItem): d['wires'].append({'type':"Wire",'start_comp_name':i.s_c[0].name if i.s_c else None,'start_term_id':i.s_c[1] if i.s_c else None,'end_comp_name':i.e_c[0].name if i.e_c else None,'end_term_id':i.e_c[1] if i.e_c else None})
        try:
            with open(fn,'w') as f: json.dump(d,f,indent=4)
            if not (hasattr(self.sender(), 'text') and self.sender().text() == 'Add to &Favorites...'):
                 QMessageBox.information(self,"Circuit Saved",f"Circuit saved to:\n{fn}")
            self.statusBar().showMessage(f"Saved to {fn}",3000)
        except IOError as e:QMessageBox.warning(self,"Save Error",f"Could not save: {e}");self.statusBar().showMessage(f"Error saving: {e}",3000)
    def open_circuit(self):fn,_=QFileDialog.getOpenFileName(self,"Open",os.getcwd(),"*.json");self.open_circuit_from_file(fn) if fn else self.statusBar().showMessage("Open cancelled.",2000)
    def open_circuit_from_file(self,fn):
        if not fn: return
        try:
            with open(fn,'r') as f:cd=json.load(f)
        except Exception as e:QMessageBox.critical(self,"Error Opening Circuit",f"Could not open or parse circuit file: {e}");return
        self.scene.clear();self.pw.clear_properties();BaseComponentItem.item_counters.clear();self._cleanup_temp_files();self.ac_analysis_params=None;item_by_name_map={}
        for comp_d in cd.get('components',[]):
            ct=comp_d.get('type');itm=None;n=comp_d.get('name');v=comp_d.get('value',"")
            if ct==ResistorItem.COMPONENT_TYPE: itm=ResistorItem(n,v)
            elif ct==VoltageSourceItem.COMPONENT_TYPE: itm=VoltageSourceItem(n,v,comp_d.get('source_type',"DC"),comp_d.get('ac_magnitude',"1"),comp_d.get('ac_phase',"0"))
            elif ct==CapacitorItem.COMPONENT_TYPE: itm=CapacitorItem(n,v)
            elif ct==InductorItem.COMPONENT_TYPE: itm=InductorItem(n,v)
            elif ct==GroundComponentItem.COMPONENT_TYPE: itm=GroundComponentItem(n)
            if itm: itm.setPos(QPointF(comp_d.get('pos_x',0),comp_d.get('pos_y',0)));itm.setRotation(comp_d.get('rotation',0));self.scene.addItem(itm);item_by_name_map[n]=itm
        for wd in cd.get('wires',[]):
            sc,ec=item_by_name_map.get(wd.get('start_comp_name')),item_by_name_map.get(wd.get('end_comp_name'));st_id,et_id=wd.get('start_term_id'),wd.get('end_term_id')
            if sc and ec and st_id is not None and et_id is not None:
                vs_t = hasattr(sc,'local_terminals') and st_id in sc.local_terminals; ve_t = hasattr(ec,'local_terminals') and et_id in ec.local_terminals
                if vs_t and ve_t: sconn=(sc,st_id);econn=(ec,et_id);w=WireItem(sconn,econn);self.scene.addItem(w);sc.connect_wire(st_id,w);ec.connect_wire(et_id,w)
        self.current_filename=fn if os.path.dirname(os.path.abspath(fn))!=os.path.abspath(self.FAVORITES_DIR) else None;self.statusBar().showMessage(f"Loaded {os.path.basename(fn)}",5000);self.setWindowTitle(f"Schematic Editor - {os.path.basename(fn)}")
    def add_to_favorites(self):
        fav_n=os.path.splitext(os.path.basename(self.current_filename))[0] if self.current_filename else ""; t,ok=QInputDialog.getText(self,"Add Favorite","Name for favorite:",QLineEdit.Normal,fav_n)
        if ok and t:ffn=os.path.join(self.FAVORITES_DIR,t.replace(" ","_")+".json");self.save_circuit_to_file(ffn);QMessageBox.information(self,"Favorite Saved",f"Circuit '{t}' saved to favorites.")
        else:self.statusBar().showMessage("Add favorite cancelled.",2000)
    def open_favorite(self):
        if not os.path.exists(self.FAVORITES_DIR) or not os.listdir(self.FAVORITES_DIR):QMessageBox.information(self,"No Favorites","Favorites directory not found or is empty.");return
        favs=[f for f in os.listdir(self.FAVORITES_DIR) if f.endswith(".json")];
        if not favs:QMessageBox.information(self,"No Favorites","No circuit files found in favorites.");return
        fav_ns=[os.path.splitext(f)[0] for f in favs];cfn,ok=QInputDialog.getItem(self,"Open Favorite","Select a favorite circuit:",fav_ns,0,False);self.open_circuit_from_file(os.path.join(self.FAVORITES_DIR,cfn+".json")) if ok and cfn else self.statusBar().showMessage("Open favorite cancelled.",2000)
    def closeEvent(self,event):self._cleanup_temp_files();super().closeEvent(event)
    def _cleanup_temp_files(self):[os.remove(fp) for fp in list(self.temp_files_to_cleanup) if os.path.exists(fp)];self.temp_files_to_cleanup.clear()

def main():
    is_headless_test = os.environ.get("RUN_HEADLESS_TEST") == "true"
    if is_headless_test:
        print("RUN_HEADLESS_TEST is true. Attempting to run SchematicEditor logic for diagnostics.")

    app=QApplication(sys.argv)
    editor=SchematicEditor()

    if is_headless_test:
        diag_output_filename = "diagnostic_output.txt"
        print(f"Diagnostic output will be written to: {os.path.abspath(diag_output_filename)}")
        try:
            with open(diag_output_filename, "w") as diag_file:
                diag_file.write("Starting HEADLESS diagnostic run for SchematicEditor KCL test.\n")
                test_circuit_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_circuits", "voltage_divider_symbolic.json")
                if os.path.exists(test_circuit_path):
                    diag_file.write(f"Loading test circuit: {test_circuit_path}\n")
                    editor.open_circuit_from_file(test_circuit_path)
                    diag_file.write("Running simulation...\n")
                    editor.run_simulation()
                    diag_file.write("\n--- Solver Log (SchematicEditor Headless) ---\n")
                    diag_file.write(editor.solver_log_output_area.toPlainText() + "\n")
                    diag_file.write("\n--- Solution Path & KCL (SchematicEditor Headless) ---\n")
                    diag_file.write(editor.solution_path_area.toPlainText() + "\n")
                    diag_file.write("\n--- Parsed Measures (SchematicEditor Headless) ---\n")
                    diag_file.write(json.dumps(editor.parsed_measure_results, indent=2) + "\n")
                else:
                    diag_file.write(f"Test circuit not found: {test_circuit_path}\n")
                diag_file.write("Headless diagnostic run complete. Exiting.\n")
        except Exception as e:
            try:
                with open(diag_output_filename, "a") as diag_file_exc:
                    diag_file_exc.write(f"\n!!! EXCEPTION DURING HEADLESS RUN: {type(e).__name__}: {e} !!!\n")
                    import traceback
                    traceback.print_exc(file=diag_file_exc)
            except:
                 print(f"!!! EXCEPTION DURING HEADLESS RUN: {type(e).__name__}: {e} !!!")
                 traceback.print_exc()
        finally:
            sys.exit(0)

    editor.show()
    sys.exit(app.exec_())

if __name__=='__main__':
    main()
