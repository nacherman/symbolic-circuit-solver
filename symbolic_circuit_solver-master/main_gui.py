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
                             QDialogButtonBox)
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
            numeric_part_str = value_str[:-len(suffix)]
            try:
                numeric_part = float(numeric_part_str)
                return numeric_part * multiplier
            except ValueError: return value_str
    try: return float(value_str)
    except ValueError: return value_str

class BaseComponentItem(QGraphicsItem):
    item_counters = {}
    TERMINAL_A = 0; TERMINAL_B = 1
    def __init__(self, name=None, value="1", default_prefix="X", num_terminals=2, parent=None):
        super().__init__(parent)
        component_type = getattr(self, 'COMPONENT_TYPE', 'Unknown')
        if component_type not in BaseComponentItem.item_counters: BaseComponentItem.item_counters[component_type] = 0
        if name is None:
            BaseComponentItem.item_counters[component_type] += 1
            self._name = f"{default_prefix}{BaseComponentItem.item_counters[component_type]}"
        else: self._name = name
        self._value = value
        self.setFlag(QGraphicsItem.ItemIsSelectable); self.setFlag(QGraphicsItem.ItemIsMovable); self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.font=QFont("Arial",8); self.terminal_radius=4; self.snap_radius=10; self.width=60; self.height=30; self.lead_length=20
        self.local_terminals={}; self.terminal_connections={}
        for i in range(num_terminals): self.terminal_connections[i]=[]
    @property
    def name(self): return self._name
    def set_name(self, new_name):
        if self._name != new_name:
            if self.scene() and hasattr(self.scene(), 'component_name_changed'):
                self.scene().component_name_changed(self, self._name, new_name)
            self.prepareGeometryChange(); self._name = new_name; self.update()
    @property
    def value(self): return self._value
    def set_value(self, new_value):
        if self._value != new_value: self.prepareGeometryChange(); self._value = new_value; self.update()

    def common_paint_text_and_selection(self, painter, text_ref_rect_local=None, selection_rect_local=None, show_plus_minus=False):
        painter.setFont(self.font); painter.setPen(Qt.black)
        ref_rect = text_ref_rect_local if text_ref_rect_local else QRectF(-self.width/2, -self.height/2, self.width, self.height)
        name_y_pos = ref_rect.top() - painter.fontMetrics().height() - 2
        painter.drawText(QRectF(ref_rect.left(), name_y_pos, ref_rect.width(), painter.fontMetrics().height()), Qt.AlignCenter, self.name)
        display_value_str = ""
        if hasattr(self, 'COMPONENT_TYPE') and self.COMPONENT_TYPE == VoltageSourceItem.COMPONENT_TYPE:
            vs_item = self
            if vs_item.source_type == "AC":
                display_value_str = f"AC:{vs_item.ac_magnitude}V {vs_item.ac_phase}°"
                if vs_item.value and vs_item.value != "0": display_value_str += f"\nDC:{vs_item.value}V"
            else: display_value_str = f"DC:{vs_item.value}V"
        elif not hasattr(self, 'COMPONENT_TYPE') or self.COMPONENT_TYPE != GroundComponentItem.COMPONENT_TYPE:
            display_value_str = self.value
        if display_value_str:
            value_y_pos = ref_rect.bottom() + 2
            painter.drawText(QRectF(ref_rect.left(), value_y_pos, ref_rect.width(), painter.fontMetrics().height()*2.2), Qt.AlignCenter | Qt.AlignTop | Qt.TextWordWrap, display_value_str)
        terminal_brush=QBrush(Qt.black); painter.setPen(QPen(Qt.black,1)); painter.setBrush(terminal_brush)
        for t_pos in self.local_terminals.values(): painter.drawEllipse(t_pos,self.terminal_radius,self.terminal_radius)
        if show_plus_minus and hasattr(self,'TERMINAL_PLUS') and hasattr(self,'TERMINAL_MINUS') and self.TERMINAL_PLUS in self.local_terminals and self.TERMINAL_MINUS in self.local_terminals:
            plus_pos=self.local_terminals[self.TERMINAL_PLUS]; minus_pos=self.local_terminals[self.TERMINAL_MINUS]
            painter.setPen(QPen(Qt.black,1.5)); font_metric=painter.fontMetrics(); char_h_offset = font_metric.horizontalAdvance('+')/2 ;char_v_offset=font_metric.ascent()/2
            painter.drawText(plus_pos+QPointF(self.terminal_radius+2 if plus_pos.x()==0 else -char_h_offset,char_v_offset if plus_pos.x()!=0 else (self.terminal_radius+2 if plus_pos.y()<0 else -self.terminal_radius-font_metric.height()+char_v_offset)),"+")
            painter.drawText(minus_pos+QPointF(self.terminal_radius+2 if minus_pos.x()==0 else -char_h_offset,char_v_offset if minus_pos.x()!=0 else (self.terminal_radius+2 if minus_pos.y()<0 else -self.terminal_radius-font_metric.height()+char_v_offset)),"-")
        if self.isSelected(): pen=QPen(Qt.blue,1,Qt.DashLine); painter.setPen(pen); painter.setBrush(Qt.NoBrush); painter.drawRect(selection_rect_local if selection_rect_local else self.boundingRect().adjusted(-1,-1,1,1))
    def paint_terminals(self, painter):
        terminal_brush = QBrush(Qt.black); painter.setPen(QPen(Qt.black, 1)); painter.setBrush(terminal_brush)
        for t_pos in self.local_terminals.values(): painter.drawEllipse(t_pos, self.terminal_radius, self.terminal_radius)
    def rotate_item(self, angle_degrees=90): self.setRotation(self.rotation()+angle_degrees)
    def get_terminal_scene_positions(self): return {tid:self.mapToScene(pos) for tid,pos in self.local_terminals.items()}
    def connect_wire(self, terminal_id, wire_item):
        if terminal_id in self.terminal_connections and wire_item not in self.terminal_connections[terminal_id]: self.terminal_connections[terminal_id].append(wire_item)
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
    COMPONENT_TYPE = "Resistor"
    def __init__(self, name=None, value="1k", parent=None):
        super().__init__(name,value,"R",2,parent); self.local_terminals={self.TERMINAL_A:QPointF(-self.width/2-self.lead_length,0),self.TERMINAL_B:QPointF(self.width/2+self.lead_length,0)}
    def boundingRect(self): text_offset_y=18;text_offset_x=5;max_x=self.width/2+self.lead_length+self.terminal_radius+text_offset_x;max_y=self.height/2+text_offset_y+self.terminal_radius;diag=(max_x**2+max_y**2)**0.5;return QRectF(-diag,-diag,2*diag,2*diag)
    def paint(self,painter,option,widget=None):
        painter.setRenderHint(QPainter.Antialiasing);body_rect=QRectF(-self.width/2,-self.height/2,self.width,self.height)
        painter.setPen(QPen(Qt.black,2));painter.setBrush(QBrush(Qt.white));painter.drawRect(body_rect);painter.setPen(QPen(Qt.black,2))
        painter.drawLine(QPointF(-self.width/2,0),self.local_terminals[self.TERMINAL_A]);painter.drawLine(QPointF(self.width/2,0),self.local_terminals[self.TERMINAL_B])
        self.paint_terminals(painter);sel_rect=QRectF(-self.width/2-self.lead_length-3,-self.height/2-3,self.width+2*self.lead_length+6,self.height+6)
        self.common_paint_text_and_selection(painter,body_rect,sel_rect)

class VoltageSourceItem(BaseComponentItem):
    COMPONENT_TYPE="VoltageSource";TERMINAL_PLUS=BaseComponentItem.TERMINAL_A;TERMINAL_MINUS=BaseComponentItem.TERMINAL_B
    def __init__(self,name=None,value="1",source_type="DC",ac_magnitude="1",ac_phase="0",parent=None):
        super().__init__(name,value,"V",2,parent);self.source_type=source_type;self.ac_magnitude=ac_magnitude;self.ac_phase=ac_phase
        self.radius=20;self.width=self.radius*2;self.height=self.radius*2
        self.local_terminals={self.TERMINAL_PLUS:QPointF(0,-self.radius-self.lead_length),self.TERMINAL_MINUS:QPointF(0,self.radius+self.lead_length)}
    def set_source_type(self,t): self.source_type=t;self.update()
    def set_ac_magnitude(self,m): self.ac_magnitude=m;self.update()
    def set_ac_phase(self,p): self.ac_phase=p;self.update()
    def get_spice_value_string(self):
        if self.source_type == "AC":
            val_str = self.ac_magnitude
            if self.value and self.value != "0" and self.value.strip() != "":
                val_str = f"DC {self.value} AC {self.ac_magnitude} {self.ac_phase}"
            else:
                val_str = f"AC {self.ac_magnitude} {self.ac_phase}"
            return val_str
        return self.value
    def boundingRect(self):text_offset_y=18;text_offset_x=15;max_x=self.radius+self.terminal_radius+text_offset_x;max_y=self.radius+self.lead_length+self.terminal_radius+text_offset_y;diag=(max_x**2+max_y**2)**0.5;return QRectF(-diag,-diag,2*diag,2*diag)
    def paint(self,painter,option,widget=None):
        painter.setRenderHint(QPainter.Antialiasing);circle_rect=QRectF(-self.radius,-self.radius,2*self.radius,2*self.radius)
        painter.setPen(QPen(Qt.black,2));painter.setBrush(QBrush(Qt.white));painter.drawEllipse(circle_rect)
        if self.source_type=="AC":
            path=QPainterPath();path.moveTo(-self.radius*0.6,0);path.quadTo(-self.radius*0.3,-self.radius*0.5,0,0);path.quadTo(self.radius*0.3,self.radius*0.5,self.radius*0.6,0)
            painter.setPen(QPen(Qt.black,1.5));painter.drawPath(path)
        else:
            pen_sign=QPen(Qt.black,1.5);painter.setPen(pen_sign);sign_len=self.radius*0.4
            painter.drawLine(QPointF(-sign_len,0),QPointF(sign_len,0))
            if not (str(self.value).startswith('-')): painter.drawLine(QPointF(0,-sign_len),QPointF(0,sign_len))
        painter.setPen(QPen(Qt.black,2));painter.drawLine(QPointF(0,-self.radius),self.local_terminals[self.TERMINAL_PLUS]);painter.drawLine(QPointF(0,self.radius),self.local_terminals[self.TERMINAL_MINUS])
        self.paint_terminals(painter);text_ref_rect=QRectF(-self.width/2,-self.height/2,self.width,self.height)
        sel_rect=circle_rect.adjusted(-self.lead_length-5,-self.lead_length-5,self.lead_length+5,self.lead_length+5)
        self.common_paint_text_and_selection(painter,text_ref_rect,sel_rect,show_plus_minus=True)

class CapacitorItem(BaseComponentItem):
    COMPONENT_TYPE="Capacitor"
    def __init__(self,name=None,value="1u",parent=None):super().__init__(name,value,"C",2,parent);self.plate_spacing=8;self.plate_length=self.height;self.width=self.plate_spacing+2*self.lead_length;self.local_terminals={self.TERMINAL_A:QPointF(-self.plate_spacing/2-self.lead_length,0),self.TERMINAL_B:QPointF(self.plate_spacing/2+self.lead_length,0)}
    def boundingRect(self):text_offset_y=18;text_offset_x=5;max_x=self.width/2+self.terminal_radius+text_offset_x;max_y=self.plate_length/2+text_offset_y+self.terminal_radius;diag=(max_x**2+max_y**2)**0.5;return QRectF(-diag,-diag,2*diag,2*diag)
    def paint(self,painter,option,widget=None):
        painter.setRenderHint(QPainter.Antialiasing);painter.setPen(QPen(Qt.black,2));p1x=-self.plate_spacing/2;p2x=self.plate_spacing/2
        painter.drawLine(self.local_terminals[self.TERMINAL_A],QPointF(p1x,0));painter.drawLine(QPointF(p1x,-self.plate_length/2),QPointF(p1x,self.plate_length/2))
        painter.drawLine(self.local_terminals[self.TERMINAL_B],QPointF(p2x,0));painter.drawLine(QPointF(p2x,-self.plate_length/2),QPointF(p2x,self.plate_length/2))
        self.paint_terminals(painter);text_ref_rect=QRectF(-self.width/2,-self.height/2,self.width,self.height)
        sel_rect=QRectF(self.local_terminals[self.TERMINAL_A].x()-3,-self.plate_length/2-3,(self.local_terminals[self.TERMINAL_B].x()-self.local_terminals[self.TERMINAL_A].x())+6,self.plate_length+6)
        self.common_paint_text_and_selection(painter,text_ref_rect,sel_rect)

class InductorItem(BaseComponentItem):
    COMPONENT_TYPE="Inductor"
    def __init__(self,name=None,value="1mH",parent=None):super().__init__(name,value,"L",2,parent);self.num_loops=3;self.loop_radius=self.height/2;self.coil_width=self.num_loops*self.loop_radius*0.8;self.width=self.coil_width+2*self.lead_length;self.local_terminals={self.TERMINAL_A:QPointF(-self.coil_width/2-self.lead_length,0),self.TERMINAL_B:QPointF(self.coil_width/2+self.lead_length,0)}
    def boundingRect(self):text_offset_y=18;text_offset_x=5;max_x=self.width/2+self.terminal_radius+text_offset_x;max_y=self.height/2+text_offset_y+self.terminal_radius;diag=(max_x**2+max_y**2)**0.5;return QRectF(-diag,-diag,2*diag,2*diag)
    def paint(self,painter,option,widget=None):
        painter.setRenderHint(QPainter.Antialiasing);painter.setPen(QPen(Qt.black,2));painter.drawLine(self.local_terminals[self.TERMINAL_A],QPointF(-self.coil_width/2,0))
        path=QPainterPath();path.moveTo(-self.coil_width/2,0);loop_w=self.coil_width/self.num_loops
        for i in range(self.num_loops):path.arcTo(-self.coil_width/2+i*loop_w,-self.loop_radius,loop_w,2*self.loop_radius,180.0,-180.0)
        painter.drawPath(path);painter.drawLine(QPointF(self.coil_width/2,0),self.local_terminals[self.TERMINAL_B]);self.paint_terminals(painter)
        text_ref_rect=QRectF(-self.coil_width/2,-self.height/2,self.coil_width,self.height)
        sel_rect=QRectF(self.local_terminals[self.TERMINAL_A].x()-3,-self.loop_radius-3,(self.local_terminals[self.TERMINAL_B].x()-self.local_terminals[self.TERMINAL_A].x())+6,2*self.loop_radius+6)
        self.common_paint_text_and_selection(painter,text_ref_rect,sel_rect)

class GroundComponentItem(BaseComponentItem):
    COMPONENT_TYPE="Ground";TERMINAL_CONNECTION=BaseComponentItem.TERMINAL_A
    def __init__(self,name=None,parent=None):super().__init__(name,"","GND",1,parent);self.width=30;self.height=20;self.local_terminals={self.TERMINAL_CONNECTION:QPointF(0,-self.height/2)}
    def boundingRect(self):return QRectF(-self.width/2,-self.height/2-15,self.width,self.height+25)
    def paint(self,painter,option,widget=None):
        painter.setRenderHint(QPainter.Antialiasing);painter.setPen(QPen(Qt.black,2));p1=self.local_terminals[self.TERMINAL_CONNECTION];p2=QPointF(p1.x(),p1.y()+self.height);painter.drawLine(p1,p2)
        line_len=self.width*0.8
        for i in range(3):y_pos=p2.y()-i*(self.height/3.5);painter.drawLine(QPointF(p1.x()-line_len/2,y_pos),QPointF(p1.x()+line_len/2,y_pos));line_len*=0.7
        self.paint_terminals(painter)
        text_ref_rect = QRectF(-self.width/2, p1.y() - 15 - 5, self.width, 15)
        self.common_paint_text_and_selection(painter, text_ref_rect, self.boundingRect())

class WireItem(QGraphicsItem):
    COMPONENT_TYPE = "Wire";
    def __init__(self,s_c=None,e_c=None,p=None): super().__init__(p);self.s_c=s_c;self.e_c=e_c;self.setFlag(QGraphicsItem.ItemIsSelectable);self.setZValue(-1);self.p1s=QPointF();self.p2s=QPointF();self.update_endpoints_from_connections()
    def update_endpoints_from_connections(self):
        p1,p2=QPointF(),QPointF()
        def get_tp(conn):
            if conn: c,t_id=conn; return c.mapToScene(c.local_terminals[t_id]) if c.scene() and hasattr(c,'local_terminals') and t_id in c.local_terminals else QPointF()
            return QPointF()
        p1=get_tp(self.s_c); p2=get_tp(self.e_c)
        if self.p1s!=p1 or self.p2s!=p2: self.prepareGeometryChange();self.p1s=p1;self.p2s=p2;self.update()
    def get_scene_points(self): return self.p1s,self.p2s
    def boundingRect(self): return QRectF(self.mapFromScene(self.p1s),self.mapFromScene(self.p2s)).normalized().adjusted(-5,-5,5,5) if not (self.p1s.isNull() or self.p2s.isNull()) else QRectF()
    def paint(self,painter,option,widget=None):
        if self.p1s.isNull() or self.p2s.isNull(): return
        painter.setRenderHint(QPainter.Antialiasing);pen=QPen(Qt.darkCyan,2)
        if self.isSelected(): pen.setColor(Qt.blue);pen.setStyle(Qt.DashLine)
        painter.setPen(pen);painter.drawLine(self.mapFromScene(self.p1s),self.mapFromScene(self.p2s))
    def cleanup_connections(self):
        def dc(conn):
            if conn: c,t_id=conn; c.disconnect_wire(t_id,self) if hasattr(c,'disconnect_wire') else None
        dc(self.s_c); dc(self.e_c); self.s_c=None; self.e_c=None

class SchematicView(QGraphicsView):
    def __init__(self,s,p=None):super().__init__(s,p);self.setAcceptDrops(True);self.c_t=None;self.w_s_c=None;self.t_l_i=None;self.s_c_e_i=None
    def set_tool(self,t_n): self.c_t=t_n;self.w_s_c=None;self.s_c_e_i=None;self.scene().removeItem(self.t_l_i) if self.t_l_i else None;self.t_l_i=None;self.setCursor(Qt.CrossCursor if t_n=="Wire" else Qt.ArrowCursor)
    def _get_snapped_connection_info(self,s_p_c):
        for itm in self.scene().items():
            if isinstance(itm,BaseComponentItem) and hasattr(itm,'local_terminals') and itm.COMPONENT_TYPE!="Wire":
                for t_id,t_s_p in itm.get_terminal_scene_positions().items():
                    if(t_s_p-s_p_c).manhattanLength()<itm.snap_radius*1.5:return itm,t_id,t_s_p
        return None
    def dropEvent(self,e):
        if e.mimeData().hasFormat("application/x-componentname"):
            cn=e.mimeData().data("application/x-componentname").data().decode('utf-8')
            if cn=="Wire":e.ignore();return
            dp=self.mapToScene(e.pos());itm=None
            if cn==ResistorItem.COMPONENT_TYPE:itm=ResistorItem()
            elif cn==VoltageSourceItem.COMPONENT_TYPE:itm=VoltageSourceItem()
            elif cn==CapacitorItem.COMPONENT_TYPE:itm=CapacitorItem()
            elif cn==InductorItem.COMPONENT_TYPE:itm=InductorItem()
            elif cn==GroundComponentItem.COMPONENT_TYPE:itm=GroundComponentItem()
            if itm:itm.setPos(dp);self.scene().addItem(itm)
            e.acceptProposedAction()
        else:super().dropEvent(e)
        self.set_tool(None)
    def mousePressEvent(self,e):
        sp=self.mapToScene(e.pos())
        if self.c_t=="Wire":
            if e.button()==Qt.LeftButton:
                sd=self._get_snapped_connection_info(sp)
                if self.w_s_c is None:
                    if sd:self.w_s_c=(sd[0],sd[1]); sdp=sd[2]; self.t_l_i=self.scene().addLine(QLineF(sdp,sdp),QPen(Qt.darkGray,1,Qt.DashLine))
                else:
                    ecd=self.s_c_e_i or (sd if sd else None)
                    if ecd and self.w_s_c and not (ecd[0]==self.w_s_c[0] and ecd[1]==self.w_s_c[1]):
                        w=WireItem(self.w_s_c,ecd); self.scene().addItem(w)
                        sc,st_id=self.w_s_c; ec,et_id=ecd
                        if hasattr(sc,'connect_wire'):sc.connect_wire(st_id,w)
                        if hasattr(ec,'connect_wire'):ec.connect_wire(et_id,w)
                    self.w_s_c=None; self.s_c_e_i=None; self.scene().removeItem(self.t_l_i) if self.t_l_i else None; self.t_l_i=None
            elif e.button()==Qt.RightButton: self.w_s_c=None;self.s_c_e_i=None;self.set_tool(None);self.scene().removeItem(self.t_l_i) if self.t_l_i else None; self.t_l_i=None
        else:super().mousePressEvent(e)
    def mouseMoveEvent(self,e):
        sp=self.mapToScene(e.pos())
        if self.c_t=="Wire" and self.w_s_c:
            sd=self._get_snapped_connection_info(sp); sc,st_id=self.w_s_c
            if not sc.scene() or not hasattr(sc,'local_terminals') or st_id not in sc.local_terminals: self.w_s_c=None;self.s_c_e_i=None;self.scene().removeItem(self.t_l_i) if self.t_l_i else None;self.t_l_i=None;self.set_tool(None);return
            sdp=sc.mapToScene(sc.local_terminals[st_id])
            if sd: self.s_c_e_i=(sd[0],sd[1]); dep=sd[2]
            else: self.s_c_e_i=None; dep=sp
            if self.t_l_i: self.t_l_i.setLine(QLineF(sdp,dep))
        else:super().mouseMoveEvent(e)
    def keyPressEvent(self,e):
        si=self.scene().selectedItems()
        if e.key()==Qt.Key_R: [itm.rotate_item(90) for itm in si if hasattr(itm,'rotate_item')] if si else super().keyPressEvent(e)
        elif e.key()==Qt.Key_Delete or e.key()==Qt.Key_Backspace:
            if si:
                for itm in list(si):
                    if isinstance(itm,WireItem): itm.cleanup_connections()
                    elif isinstance(itm,BaseComponentItem): [w.cleanup_connections() or (self.scene().removeItem(w) if w.scene() else None) for tid_k in list(itm.terminal_connections.keys()) for w in list(itm.terminal_connections[tid_k])]
                    if itm.scene(): self.scene().removeItem(itm)
            else:super().keyPressEvent(e)
        elif e.key()==Qt.Key_Escape:
            if self.c_t=="Wire":
                self.w_s_c=None; self.s_c_e_i=None
                if self.t_l_i: self.scene().removeItem(self.t_l_i)
                self.t_l_i=None
            self.set_tool(None)
        else:super().keyPressEvent(e)
    def dragEnterEvent(self,e): cn=e.mimeData().data("application/x-componentname").data().decode('utf-8') if e.mimeData().hasFormat("application/x-componentname") else None; (self.set_tool(None) or e.acceptProposedAction()) if cn and cn!="Wire" else (e.ignore() if cn=="Wire" else super().dragEnterEvent(e))
    def dragMoveEvent(self,e): e.acceptProposedAction() if e.mimeData().hasFormat("application/x-componentname") else super().dragMoveEvent(e)

class ComponentListWidget(QListWidget):
    def __init__(self,p=None):super().__init__(p);self.setDragEnabled(True);self.addItems([ResistorItem.COMPONENT_TYPE,VoltageSourceItem.COMPONENT_TYPE,CapacitorItem.COMPONENT_TYPE,InductorItem.COMPONENT_TYPE,GroundComponentItem.COMPONENT_TYPE,"Wire"]);self.itemClicked.connect(self.on_item_clicked);self.parent_view=None
    def set_schematic_view(self,v):self.parent_view=v
    def on_item_clicked(self,itm): (self.parent_view.set_tool("Wire") if itm.text()=="Wire" else (self.parent_view.set_tool(None) if self.parent_view.current_tool=="Wire" else None)) if self.parent_view else None
    def startDrag(self,sa):itm=self.currentItem();(md:=QMimeData(),md.setData("application/x-componentname",itm.text().encode('utf-8')),(d:=QDrag(self)).setMimeData(md),(self.parent_view.set_tool(None) if self.parent_view and self.parent_view.current_tool=="Wire" else None),d.exec_(sa)) if itm and itm.text()!="Wire" else super().startDrag(Qt.IgnoreAction)

class PropertiesWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.layout=QFormLayout(self); self.current_item=None
        self.name_edit=QLineEdit(); self.layout.addRow("Name:",self.name_edit)
        self.value_label=QLabel("Value (DC):"); self.value_edit=QLineEdit(); self.layout.addRow(self.value_label,self.value_edit)
        self.source_type_combo=QComboBox(); self.source_type_combo.addItems(["DC","AC"])
        self.ac_mag_edit=QLineEdit(); self.ac_phase_edit=QLineEdit("0")
        self.vs_specific_widgets = []
        self.vs_specific_rows_indices = []
        vs_row1 = self.layout.rowCount(); self.layout.addRow("Source Type:", self.source_type_combo); self.vs_specific_rows_indices.append(vs_row1)
        vs_row2 = self.layout.rowCount(); self.layout.addRow("AC Magnitude:", self.ac_mag_edit); self.vs_specific_rows_indices.append(vs_row2)
        vs_row3 = self.layout.rowCount(); self.layout.addRow("AC Phase (deg):", self.ac_phase_edit); self.vs_specific_rows_indices.append(vs_row3)
        self.name_edit.editingFinished.connect(self.on_name_changed); self.value_edit.editingFinished.connect(self.on_value_changed)
        self.source_type_combo.currentIndexChanged.connect(self.on_source_type_changed)
        self.ac_mag_edit.editingFinished.connect(self.on_ac_mag_changed); self.ac_phase_edit.editingFinished.connect(self.on_ac_phase_changed)
        self.clear_properties()
    def set_current_item(self,item):
        self.current_item=item; is_editable_base_comp=isinstance(item,BaseComponentItem) and item.COMPONENT_TYPE!="Wire"
        self.name_edit.setEnabled(is_editable_base_comp)
        if is_editable_base_comp:
            self.name_edit.setText(item.name); is_gnd=item.COMPONENT_TYPE==GroundComponentItem.COMPONENT_TYPE
            is_vs=isinstance(item,VoltageSourceItem)
            self.value_edit.setEnabled(not is_gnd); self.value_label.setVisible(not is_gnd); self.value_edit.setVisible(not is_gnd)
            if is_gnd: self.value_edit.setText("")
            elif is_vs: self.value_edit.setText(item.value); self.source_type_combo.setCurrentText(item.source_type); self.ac_mag_edit.setText(item.ac_magnitude); self.ac_phase_edit.setText(item.ac_phase)
            else: self.value_edit.setText(item.value)
            for row_idx in self.vs_specific_rows_indices: self.layout.setRowVisible(row_idx, is_vs)
            if is_vs: self.on_source_type_changed()
        else: self.clear_properties()
    def clear_properties(self):
        self.current_item=None;self.name_edit.setText("");self.value_edit.setText("");self.name_edit.setEnabled(False);self.value_edit.setEnabled(False);self.value_label.setText("Value:")
        self.value_label.setVisible(True); self.value_edit.setVisible(True)
        for row_idx in self.vs_specific_rows_indices: self.layout.setRowVisible(row_idx, False)
        self.source_type_combo.setCurrentIndex(0);self.ac_mag_edit.setText("");self.ac_phase_edit.setText("0")
    def on_name_changed(self):
        if self.current_item and hasattr(self.current_item,'set_name'):self.current_item.set_name(self.name_edit.text())
    def on_value_changed(self):
        if self.current_item and hasattr(self.current_item,'set_value') and (not hasattr(self.current_item,'COMPONENT_TYPE') or self.current_item.COMPONENT_TYPE!=GroundComponentItem.COMPONENT_TYPE): self.current_item.set_value(self.value_edit.text())
    def on_source_type_changed(self):
        if self.current_item and isinstance(self.current_item,VoltageSourceItem):
            st=self.source_type_combo.currentText(); self.current_item.set_source_type(st); is_ac=(st=="AC")
            self.layout.setRowVisible(self.vs_specific_rows_indices[1], is_ac)
            self.layout.setRowVisible(self.vs_specific_rows_indices[2], is_ac)
            self.value_label.setText("DC Value/Offset:" if is_ac else "DC Value:")
    def on_ac_mag_changed(self):
        if self.current_item and isinstance(self.current_item,VoltageSourceItem):self.current_item.set_ac_magnitude(self.ac_mag_edit.text())
    def on_ac_phase_changed(self):
        if self.current_item and isinstance(self.current_item,VoltageSourceItem):self.current_item.set_ac_phase(self.ac_phase_edit.text())

class ACAnalysisDialog(QDialog):
    def __init__(self,p=None,curr_p=None):super().__init__(p);self.setWindowTitle("AC Analysis Settings");layout=QFormLayout(self);self.stc=QComboBox();self.stc.addItems(["DEC","LIN","OCT"]);self.pe=QLineEdit("10");self.fse=QLineEdit("1");self.fspe=QLineEdit("1M");layout.addRow("Sweep:",self.stc);layout.addRow("Pts:",self.pe);layout.addRow("Fstart:",self.fse);layout.addRow("Fstop:",self.fspe);self.btns=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);self.btns.accepted.connect(self.accept);self.btns.rejected.connect(self.reject);layout.addWidget(self.btns);self.populate(curr_p) if curr_p else None
    def populate(self,p):self.stc.setCurrentText(p.get('type','DEC'));self.pe.setText(p.get('points','10'));self.fse.setText(p.get('fstart','1'));self.fspe.setText(p.get('fstop','1M'))
    def get_params(self):return{'type':self.stc.currentText(),'points':self.pe.text(),'fstart':self.fse.text(),'fstop':self.fspe.text()}

class SchematicEditor(QMainWindow):
    FAVORITES_DIR = "circuits/favorites"
    def __init__(self):
        super().__init__(); self.current_filename=None; self.temp_files_to_cleanup=[]; self.ac_analysis_params=None; self.initUI(); self.parsed_measure_results={}
        os.makedirs(self.FAVORITES_DIR, exist_ok=True)
    def initUI(self):
        self.setWindowTitle('Schematic Editor'); self.setGeometry(100,100,1600,900); self.scene=QGraphicsScene(self)
        self.scene.setSceneRect(-400,-300,800,600); self.scene.selectionChanged.connect(self.on_scene_selection_changed)
        self.schematic_view=SchematicView(self.scene,self); self.schematic_view.setFrameShape(QFrame.StyledPanel)
        self.schematic_view.setRenderHint(QPainter.Antialiasing); self.setCentralWidget(self.schematic_view)
        cd=QDockWidget("Components",self);self.cl=ComponentListWidget();self.cl.set_schematic_view(self.schematic_view);cd.setWidget(self.cl);self.addDockWidget(Qt.LeftDockWidgetArea,cd)
        pd=QDockWidget("Properties",self);self.pw=PropertiesWidget();pd.setWidget(self.pw);self.addDockWidget(Qt.RightDockWidgetArea,pd);self.pw.clear_properties()
        self.ot=QTabWidget();self.sloa=QTextEdit();self.sloa.setReadOnly(True);self.sloa.setFont(QFont("Monospace",9));self.ot.addTab(self.sloa,"Solver Log & Raw Output")
        self.mrt=QTableWidget();self.mrt.setColumnCount(3);self.mrt.setHorizontalHeaderLabels(["Name","Expression","Result"]);self.mrt.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);self.mrt.setEditTriggers(QTableWidget.NoEditTriggers);self.ot.addTab(self.mrt,"Measured Results")
        self.ptwc=QWidget();self.plo=QVBoxLayout(self.ptwc);self.psa=QScrollArea();self.psa.setWidgetResizable(True);self.psa.setWidget(self.ptwc);self.ot.addTab(self.psa,"Plots")
        self.spa=QTextEdit();self.spa.setReadOnly(True);self.spa.setFont(QFont("Monospace",9));self.ot.addTab(self.spa,"Solution Path / Analysis Steps")
        od=QDockWidget("Output & Formulas",self);od.setWidget(self.ot);self.addDockWidget(Qt.BottomDockWidgetArea,od)
        mb=self.menuBar();fm=mb.addMenu('&File');opA=QAction('&Open Circuit...',self);opA.setShortcut('Ctrl+O');opA.setToolTip("Open a circuit from a .json file");opA.triggered.connect(self.open_circuit);fm.addAction(opA)
        svA=QAction('&Save Circuit',self);svA.setShortcut('Ctrl+S');svA.setToolTip("Save the current circuit");svA.triggered.connect(self.save_circuit);fm.addAction(svA)
        sasA=QAction('Save Circuit &As...',self);sasA.setShortcut('Ctrl+Shift+S');sasA.setToolTip("Save the current circuit to a new file");sasA.triggered.connect(self.save_circuit_as);fm.addAction(sasA);fm.addSeparator()
        afA=QAction('Add to &Favorites...',self);afA.setToolTip("Save the current circuit to your favorites");afA.triggered.connect(self.add_to_favorites);fm.addAction(afA)
        ofA=QAction('Open &Favorite...',self);ofA.setToolTip("Open a circuit from your favorites");ofA.triggered.connect(self.open_favorite);fm.addAction(ofA)
        fm.addSeparator();exA=QAction('&Exit',self);exA.setShortcut('Ctrl+Q');exA.setToolTip("Exit the application");exA.triggered.connect(self.close);fm.addAction(exA)
        cm=mb.addMenu('&Circuit');rsA=QAction('&Run Simulation',self);rsA.setToolTip("Run simulation on the current circuit");rsA.triggered.connect(self.run_simulation);cm.addAction(rsA)
        sacA=QAction('Set &AC Analysis...',self);sacA.setToolTip("Configure AC analysis parameters");sacA.triggered.connect(self.set_ac_analysis_dialog);cm.addAction(sacA)
        self.statusBar().showMessage('Ready.')
    def set_ac_analysis_dialog(self):
        dialog = ACAnalysisDialog(self, self.ac_analysis_params)
        if dialog.exec_() == QDialog.Accepted: self.ac_analysis_params = dialog.get_params(); self.statusBar().showMessage(f"AC Set: {self.ac_analysis_params['type']} {self.ac_analysis_params['points']}, {self.ac_analysis_params['fstart']}-{self.ac_analysis_params['fstop']}Hz",3000)
        else: self.statusBar().showMessage("AC setup cancelled.",2000)
    def _clear_plots_tab(self):
        while self.plo.count(): child=self.plo.takeAt(0); child.widget().deleteLater() if child.widget() else None
    def _parse_and_display_measure_results(self, results_content_str):
        self.mrt.setRowCount(0); self.parsed_measure_results.clear()
        pattern = re.compile(r"""^(?P<name>\S+?):\s*(?P<expr>v\([\w\.\-\+]+\)|i\([\w\.\-\+]+\)|isub\([\w\.\-\+]+\)|[\w\.\-\+]+)\s*
---------------------
(?P<value>.+?)(?=^(?:\s*
\S+?:|\Z))""", re.MULTILINE | re.DOTALL)
        matches_found=0
        for match in pattern.finditer(results_content_str):
            matches_found+=1; data=match.groupdict(); name=data['name'].strip(); expr_str=data['expr'].strip(); value_str=data['value'].strip()
            row=self.mrt.rowCount(); self.mrt.insertRow(row)
            self.mrt.setItem(row,0,QTableWidgetItem(name)); self.mrt.setItem(row,1,QTableWidgetItem(expr_str)); self.mrt.setItem(row,2,QTableWidgetItem(value_str))
            if expr_str.startswith("v(") and expr_str.endswith(")"): self.parsed_measure_results[expr_str]=value_str
        if matches_found==0: self.mrt.insertRow(0); self.mrt.setItem(0,0,QTableWidgetItem("No .measure results.")); self.mrt.setSpan(0,0,1,3)

    def _generate_spice_netlist_string(self, netlist_components_data, final_node_names_for_all_comps, all_unique_node_names):
        spice_lines = ["* Auto-generated SPICE netlist from GUI"]
        for comp_data in netlist_components_data:
            comp_type=comp_data['type']; name=comp_data['name']; nodes=comp_data['nodes']
            value_for_spice = comp_data['value_for_spice']
            if comp_type == GroundComponentItem.COMPONENT_TYPE: continue
            node1_sp = nodes[0]; node2_sp = nodes[1] if len(nodes) > 1 else "0"
            spice_lines.append(f"{name} {node1_sp} {node2_sp} {value_for_spice}")
        if not any(c['type'] != GroundComponentItem.COMPONENT_TYPE for c in netlist_components_data): spice_lines.append("* Empty circuit (or only ground)")
        elif all_unique_node_names:
            for node_name in sorted(list(all_unique_node_names)):
                measure_name = f"vm_{node_name.replace('.','_').replace('-','neg')}"
                spice_lines.append(f".measure {measure_name} v({node_name})")
        else: spice_lines.append(".measure DUMMY_MEASURE v(0)")
        if self.ac_analysis_params: ac = self.ac_analysis_params; spice_lines.append(f".ac {ac['type']} {ac['points']} {ac['fstart']} {ac['fstop']}")
        spice_lines.append(".end"); return "\n".join(spice_lines)

    def run_simulation(self):
        self.sloa.clear(); self.mrt.setRowCount(0); self._clear_plots_tab(); self.spa.clear(); self.parsed_measure_results.clear()
        components_on_scene = [item for item in self.scene.items() if isinstance(item, BaseComponentItem) and item.COMPONENT_TYPE != "Wire"]
        if not components_on_scene: self.sloa.setText("No components."); return
        parent={}; find_set=lambda itt:parent.setdefault(itt,itt) if parent[itt]==itt else find_set(parent[itt]);
        def unite_sets(itt1,itt2): r1,r2=find_set(itt1),find_set(itt2); parent[r2]=r1 if r1!=r2 else parent[r2]
        all_comp_terms=[]; ground_terminal_reps=set()
        for comp in components_on_scene:
            if hasattr(comp,'local_terminals'):
                for term_id in comp.local_terminals.keys(): ct_tuple=(comp,term_id);find_set(ct_tuple);all_comp_terms.append(ct_tuple)
                if comp.COMPONENT_TYPE==GroundComponentItem.COMPONENT_TYPE: ground_terminal_reps.add(find_set((comp,comp.TERMINAL_CONNECTION)))
        for wire in [item for item in self.scene.items() if isinstance(item,WireItem)]:
            if wire.start_connection and wire.end_connection and wire.start_connection in parent and wire.end_connection in parent: unite_sets(wire.start_connection,wire.end_connection)
        if len(ground_terminal_reps)>1: first_gnd_rep=list(ground_terminal_reps)[0]; [unite_sets(first_gnd_rep,rep) for rep in list(ground_terminal_reps)[1:]]; ground_terminal_reps={find_set(first_gnd_rep)}
        node_map_rep_to_name={};next_node_idx=1;designated_gnd_rep=None
        if ground_terminal_reps: designated_gnd_rep=list(ground_terminal_reps)[0];node_map_rep_to_name[designated_gnd_rep]="0"
        representatives=sorted(list(set(find_set(ct) for ct in all_comp_terms)),key=lambda x:(id(x[0]),x[1]))
        all_unique_node_names_for_spice=set(node_map_rep_to_name.values())
        for rep in representatives:
            if rep not in node_map_rep_to_name:
                if designated_gnd_rep is None:node_map_rep_to_name[rep]="0";designated_gnd_rep=rep;all_unique_node_names_for_spice.add("0")
                else:node_name=f"n{next_node_idx}";next_node_idx+=1;node_map_rep_to_name[rep]=node_name;all_unique_node_names_for_spice.add(node_name)
        netlist_components_data=[];final_node_names_for_all_comps={}
        for comp in components_on_scene:
            if hasattr(comp,'local_terminals') and hasattr(comp,'COMPONENT_TYPE') and comp.COMPONENT_TYPE!="Wire":
                try:
                    comp_nodes_for_spice_line=[];term_ids_to_process=sorted(list(comp.local_terminals.keys()))
                    for term_id in term_ids_to_process:
                        rep=find_set((comp,term_id));node_name=node_map_rep_to_name.get(rep,f"unmapped_{comp.name}_t{term_id}")
                        comp_nodes_for_spice_line.append(node_name);final_node_names_for_all_comps[(comp,term_id)]=node_name
                    if comp.COMPONENT_TYPE!=GroundComponentItem.COMPONENT_TYPE:
                        spice_val = comp.get_spice_value_string() if hasattr(comp, 'get_spice_value_string') else comp.value
                        netlist_components_data.append({'type':comp.COMPONENT_TYPE,'name':comp.name,'nodes':comp_nodes_for_spice_line,'value':comp.value,'value_for_spice':spice_val})
                except KeyError as e:self.sloa.append(f"Error for {comp.name}: {e}");return
        spice_netlist_str = self._generate_spice_netlist_string(netlist_components_data, final_node_names_for_all_comps, all_unique_node_names_for_spice)
        self.spa.append("Generated SPICE Netlist (Input to Solver):\n" + spice_netlist_str + "\n\n--- Further Analysis Steps (Future Implementation) ---\n- Display of relevant circuit theory equations.\n- Step-by-step derivation for selected unknowns.\n- Visualization of Nodal/Mesh equations.")
        self.sloa.append("Generated SPICE Netlist:\n" + spice_netlist_str + "\n------------------------------------\n")
        temp_sp_filename=None; current_run_temp_files=[]
        try:
            solver_dir=os.path.dirname(os.path.abspath(__file__)); fd,temp_sp_filename=tempfile.mkstemp(suffix='.sp',prefix='gui_circuit_',text=True,dir=solver_dir)
            current_run_temp_files.append(temp_sp_filename)
            with os.fdopen(fd,'w') as tmp_sp_file: tmp_sp_file.write(spice_netlist_str);
            temp_results_base=os.path.splitext(os.path.basename(temp_sp_filename))[0]
            scs_script_path=os.path.join(solver_dir,"scs.py"); cmd=["python",scs_script_path,"-i",temp_sp_filename,"-o",os.path.join(solver_dir,temp_results_base)]
            self.sloa.append(f"Running: {' '.join(cmd)}\n")
            process=subprocess.run(cmd,capture_output=True,text=True,cwd=solver_dir,check=False)
            self.sloa.append("Solver STDOUT:\n" + (process.stdout or "<No STDOUT>"))
            self.sloa.append("\nSolver STDERR:\n" + (process.stderr or "<No STDERR>"))
            results_file_path=os.path.join(solver_dir,temp_results_base+".results"); log_file_path=os.path.join(solver_dir,temp_results_base+".log")
            current_run_temp_files.extend([results_file_path,log_file_path])
            if process.returncode==0:
                self.statusBar().showMessage("Simulation successful.",5000)
                if os.path.exists(results_file_path):
                    with open(results_file_path,'r') as f_res: results_content=f_res.read(); self.sloa.append("\n--- Raw Results File ---\n"+results_content); self._parse_and_display_measure_results(results_content)
                    self.spa.append("\n\n--- Component Analysis (Symbolic) ---\n")
                    s_sym = sympy.symbols('s')
                    for comp_data_iter in netlist_components_data:
                        comp_name = comp_data_iter['name']
                        if comp_data_iter['type'] == ResistorItem.COMPONENT_TYPE:
                            try:
                                node1_name=comp_data_iter['nodes'][0]; node2_name=comp_data_iter['nodes'][1]
                                v1_s=self.parsed_measure_results.get(f"v({node1_name})"); v2_s=self.parsed_measure_results.get(f"v({node2_name})"); r_s=comp_data_iter['value']
                                if v1_s and v2_s:
                                    v1_e=sympy.sympify(v1_s); v2_e=sympy.sympify(v2_s)
                                    r_e_val=parse_value_with_si_suffix(r_s);r_e=sympy.sympify(r_e_val) if isinstance(r_e_val,(int,float)) else sympy.symbols(r_s)
                                    vd=sympy.simplify(v1_e-v2_e); ic=sympy.simplify(vd/r_e); self.spa.append(f"Resistor {comp_name} ({r_s}): V_drop = {vd}, I = {ic}\n")
                                else: self.spa.append(f"Resistor {comp_name}: Missing node voltages.\n")
                            except Exception as e_ohm: self.spa.append(f"Error R {comp_name}: {e_ohm}\n")
                        elif comp_data_iter['type'] == CapacitorItem.COMPONENT_TYPE :
                            self.spa.append(f"Capacitor {comp_name}({comp_data_iter['value']}): " + (f"Zc = {sympy.simplify(1/(s_sym*parse_value_with_si_suffix(comp_data_iter['value'])))}" if self.ac_analysis_params and isinstance(parse_value_with_si_suffix(comp_data_iter['value']), (int,float)) else "(DC: Open)") + "\n")
                        elif comp_data_iter['type'] == InductorItem.COMPONENT_TYPE:
                            self.spa.append(f"Inductor {comp_name}({comp_data_iter['value']}): " + (f"Zl = {sympy.simplify(s_sym*parse_value_with_si_suffix(comp_data_iter['value']))}" if self.ac_analysis_params and isinstance(parse_value_with_si_suffix(comp_data_iter['value']), (int,float)) else "(DC: Short)") + "\n")
                        elif comp_data_iter['type'] == VoltageSourceItem.COMPONENT_TYPE:
                             self.spa.append(f"VoltageSource {comp_name} ({comp_data_iter['value_for_spice']}): (V from .measure)\n")
                else: self.sloa.append(f"\nERROR: Results file {results_file_path} not found.")
                plot_file_pattern=os.path.join(solver_dir,temp_results_base+"_*.png"); plot_files=glob.glob(plot_file_pattern); self._clear_plots_tab()
                if plot_files:
                    for pf in sorted(plot_files):
                        current_run_temp_files.append(pf); px=QPixmap(pf)
                        if not px.isNull(): lbl=QLabel(); lbl.setPixmap(px.scaledToWidth(self.psa.width()-30,Qt.SmoothTransformation)); self.plo.addWidget(lbl)
                        else: self.plo.addWidget(QLabel(f"Could not load: {os.path.basename(pf)}"))
                    if plot_files: self.ot.setCurrentWidget(self.psa)
                else: self.plots_layout.addWidget(QLabel("No plots generated."))
            else:
                self.statusBar().showMessage(f"Simulation failed (Code: {process.returncode}). See log.",5000)
                if os.path.exists(log_file_path):
                     with open(log_file_path,'r') as f_log: self.solver_log_output_area.append("\n--- Log (on error) ---\n"+f_log.read())
        except Exception as e: QMessageBox.critical(self,"Sim Error",f"Error: {e}"); self.solver_log_output_area.append(f"\nPYTHON ERROR: {e}")
        finally:
            for f_path in current_run_temp_files:
                if f_path not in self.temp_files_to_cleanup: self.temp_files_to_cleanup.append(f_path)

    def on_scene_selection_changed(self): si=self.scene.selectedItems(); self.properties_widget.set_current_item(si[0]) if len(si)==1 and isinstance(si[0],BaseComponentItem) and si[0].COMPONENT_TYPE!="Wire" else self.properties_widget.clear_properties()
    def save_circuit_as(self):
        start_dir = os.path.dirname(self.current_filename) if self.current_filename else os.getcwd()
        base_name = os.path.basename(self.current_filename) if self.current_filename else "untitled.json"
        filename, _ = QFileDialog.getSaveFileName(self, "Save Circuit As", os.path.join(start_dir, base_name),
                                                  "Circuit Files (*.json);;All Files (*)")
        if filename:
            self.current_filename = filename
            self.save_circuit_to_file(filename)
            self.setWindowTitle(f"Schematic Editor - {os.path.basename(filename)}")
        else: self.statusBar().showMessage("Save cancelled.", 2000)
    def save_circuit(self):
        if self.current_filename: self.save_circuit_to_file(self.current_filename)
        else: self.save_circuit_as()
    def save_circuit_to_file(self,fn):
        d={'components':[],'wires':[]};[ (d['components'].append({'type':i.COMPONENT_TYPE,'name':i.name,'value':(i.value if i.COMPONENT_TYPE!=GroundComponentItem.COMPONENT_TYPE else ""),'pos_x':i.pos().x(),'pos_y':i.pos().y(),'rotation':i.rotation(),**(({'source_type':i.source_type,'ac_magnitude':i.ac_magnitude,'ac_phase':i.ac_phase} if isinstance(i,VoltageSourceItem) else {}))}) if isinstance(i, BaseComponentItem) and i.COMPONENT_TYPE!="Wire" else (d['wires'].append({'type':i.COMPONENT_TYPE,'start_comp_name':i.s_c[0].name if i.s_c else None,'start_term_id':i.s_c[1] if i.s_c else None,'end_comp_name':i.e_c[0].name if i.e_c else None,'end_term_id':i.e_c[1] if i.e_c else None}) if isinstance(i, WireItem) else None) ) for i in self.scene.items()];
        try:
            with open(fn,'w') as f: json.dump(d,f,indent=4)
            QMessageBox.information(self,"Saved",f"Saved to:\n{fn}")
            self.statusBar().showMessage(f"Saved to {fn}",3000)
        except IOError as e: QMessageBox.warning(self,"Save Error",f"Could not save: {e}"); self.statusBar().showMessage(f"Error saving: {e}",3000)
    def open_circuit(self):
        start_dir = os.path.dirname(self.current_filename) if self.current_filename else os.getcwd()
        filename, _ = QFileDialog.getOpenFileName(self, "Open Circuit", start_dir, "Circuit Files (*.json);;All Files (*)")
        if filename: self.open_circuit_from_file(filename)
        else: self.statusBar().showMessage("Open cancelled.", 2000)
    def open_circuit_from_file(self,fn):
        try:
            with open(fn,'r') as f: cd=json.load(f)
        except Exception as e: QMessageBox.critical(self,"Error",f"Could not open/parse: {e}");return
        self.scene.clear();self.properties_widget.clear_properties();BaseComponentItem.item_counters={};self._cleanup_temp_files();self.ac_analysis_params=None;libn={}
        for comp_d in cd.get('components',[]):
            ct=comp_d.get('type');itm=None;n=comp_d.get('name');v=comp_d.get('value',"")
            if ct==ResistorItem.COMPONENT_TYPE:itm=ResistorItem(name=n,value=v)
            elif ct==VoltageSourceItem.COMPONENT_TYPE:itm=VoltageSourceItem(name=n,value=v,source_type=comp_d.get('source_type',"DC"),ac_magnitude=comp_d.get('ac_magnitude',"1"),ac_phase=comp_d.get('ac_phase',"0"))
            elif ct==CapacitorItem.COMPONENT_TYPE:itm=CapacitorItem(name=n,value=v)
            elif ct==InductorItem.COMPONENT_TYPE:itm=InductorItem(name=n,value=v)
            elif ct==GroundComponentItem.COMPONENT_TYPE:itm=GroundComponentItem(name=n)
            if itm:itm.setPos(QPointF(comp_d.get('pos_x',0),comp_d.get('py',0)));itm.setRotation(comp_d.get('r',0));self.scene.addItem(itm);libn[itm.name]=itm
        for wd in cd.get('wires',[]):
            sc,ec=libn.get(wd.get('scn')),libn.get(wd.get('ecn'));st_id,et_id=wd.get('st'),wd.get('et')
            if sc and ec and st_id is not None and et_id is not None:
                vs,ve=(hasattr(sc,'local_terminals') and st_id in sc.local_terminals),(hasattr(ec,'local_terminals') and et_id in ec.local_terminals)
                if vs and ve: sconn,econn=(sc,st_id),(ec,et_id);w=WireItem(sconn,econn);self.scene.addItem(w);(sc.connect_wire(st_id,w) if hasattr(sc,'connect_wire') else None);(ec.connect_wire(et_id,w) if hasattr(ec,'connect_wire') else None)
        self.current_filename = fn if os.path.abspath(os.path.dirname(fn)) != os.path.abspath(self.FAVORITES_DIR) else None
        self.setWindowTitle(f"Schematic Editor - {os.path.basename(fn)}"); self.statusBar().showMessage(f"Loaded {os.path.basename(fn)}",5000)
        max_counters = {};
        for name_loaded in loaded_items_by_name.keys():
            match = re.match(r"([A-Z_]+)([0-9]+)", name_loaded)
            if match:
                prefix, num_str = match.group(1), match.group(2); num = int(num_str) if num_str else 0
                comp_type_of_prefix = None
                for ct_class in [ResistorItem, VoltageSourceItem, CapacitorItem, InductorItem, GroundComponentItem]:
                    test_item_name_prefix = ct_class(default_prefix=prefix)._name
                    # Remove trailing numbers from test_item_name_prefix to get the pure prefix
                    test_prefix_match = re.match(r"([A-Z_]+)", test_item_name_prefix)
                    if test_prefix_match and name_loaded.startswith(test_prefix_match.group(1)):
                        comp_type_of_prefix = ct_class.COMPONENT_TYPE; break
                if comp_type_of_prefix:
                    if comp_type_of_prefix not in max_counters or num > max_counters[comp_type_of_prefix]: max_counters[comp_type_of_prefix] = num
        BaseComponentItem.item_counters = max_counters

    def add_to_favorites(self):
        fav_n=os.path.splitext(os.path.basename(self.current_filename))[0] if self.current_filename and os.path.dirname(self.current_filename)!=self.FAVORITES_DIR else ""; t,ok=QInputDialog.getText(self,"Add Fav","Name:",QLineEdit.Normal,fav_n)
        if ok and t:ffn=os.path.join(self.FAVORITES_DIR,t+".json");(self.save_circuit_to_file(ffn))
        else:self.statusBar().showMessage("Add fav cancelled.",2000)
    def open_favorite(self):
        if not os.path.exists(self.FAVORITES_DIR):QMessageBox.information(self,"No Favs","Dir not found.");return
        favs=[f for f in os.listdir(self.FAVORITES_DIR) if f.endswith(".json")];
        if not favs:QMessageBox.information(self,"No Favs","No circuits found.");return
        fav_ns=[os.path.splitext(f)[0] for f in favs];cfn,ok=QInputDialog.getItem(self,"Open Fav","Select:",fav_ns,0,False)
        if ok and cfn:self.open_circuit_from_file(os.path.join(self.FAVORITES_DIR,cfn+".json"))
        else:self.statusBar().showMessage("Open fav cancelled.",2000)
    def closeEvent(self,event):self._cleanup_temp_files();super().closeEvent(event)
    def _cleanup_temp_files(self): [os.remove(fp) for fp in list(self.temp_files_to_cleanup) if os.path.exists(fp)];self.temp_files_to_cleanup.clear()

def main(): app=QApplication(sys.argv);editor=SchematicEditor();editor.show();sys.exit(app.exec_())
if __name__=='__main__':main()
