"""
Class for instances of circuits

contain Instance class and all minor functions needed by it to work properly.

"""

__author__ = "Tomasz Kniola"
__credits__ = ["Tomasz Kniola"]

__license__ = "LGPL"
__version__ = "0.0.1"
__email__ = "kniola.tomasz@gmail.com"
__status__ = "development"

import sympy
import copy
import logging

import scs_errors
import scs_parser
import scs_elements

class Instance(object):
    """ Instance class

        holds object of instatiated circuits. Instance contains nets (nodes) and elements connecting nodes.
        Instances can be solved, which means that node voltages are known. Nets are split into inner nets and port nets,
        where the latter connets to nets of parent instance whose subinstance is that instance. By solving the subinstance it is said
        that voltages on nets are known only when voltages on ports are provided by parent. Full solution is thus some linear function,
        which form is obtained by solving instance, of voltage nodes.

        V - node voltage vector
        V = [Vi ; Vp]
        Vi - inner nodes voltage
        Vp - port nodes vector
        Vi = Ap*Vp + V0
        Ap - linear function matrix (Attenuation matrix)
        V0 - inner nodes voltage vector for Vp = 0
    
        By solving instance we provide thus Ap matrix and V0.
    """
    def __init__(self,parent,name,port_map={}):
        """ Initialization of Instance object

            parent: parent instance
            
            name: instance name
        
            port_map: pair of port_net parent_net names
        """
        self.port_map = port_map        
        self.elements_on_net = {}       #dictionary of list of element which are connected to net
        self.elements = {}              #dictionary of element by their names
        self.subinstances = {}          #dictionary of subinstances by their name
        self.paramsd = {}               #dictionary of parameter values by their name
        self.parent = parent            
        self.name = name                
        self.V = {}                     #dictionary of voltage values on net
        self.Vp = {}                    #dictionary of voltage values on port net
        self.V0 = {}                    #dictionary of voltage values on inner net with zero port voltage vector
        self.Ap = {}                    #dictionary form of attenuation matrix
        self.Ap_m = None                #Attenutation matrix
        self.V0_m = None                #vector of voltages on inner nets with zero port voltage vector
        self.chained_ports = {}         #dictionary of port nets which are connected by voltage sources 
        self.used_voltage_sources = []  #list of used voltage sources durring  check_voltage_loops procedure

    def add_element(self,element):
        """ Adds element to instance
            
            element: instance of element  being added to subcircuit instance

            In addition to adding element to dictionary of elements, it updates the elements_on_net dictionary                
        """
        for net in element.nets:
            if net in self.elements_on_net:
                if element not in self.elements_on_net[net]:
                    self.elements_on_net[net].append(element)
            else:
                self.elements_on_net.update({net:[element]})
        self.elements.update({element.names[0]:element})

    def add_sub_instance(self,sub_inst):
        """ Adds subinstance to instance
            
            sub_inst: instance of subinstance being added to subcircuit instance

            In addition to adding subinstance to dictionary of subinstance, it updates the elements_on_net dictionary                
        """
        for _,net in sub_inst.port_map.items():
            if net in self.elements_on_net:
                if sub_inst not in self.elements_on_net[net]:
                    self.elements_on_net[net].append(sub_inst)
            else:
                self.elements_on_net.update({net:[sub_inst]})
        self.subinstances.update({sub_inst.name:sub_inst})
    
    def nets_not_connected_to_gnd(self,connected_nets):
        """ Provides a dictionary of nets that aren't connected to ground.

            connected_nets: dictionary of nets which are already known to be connected, a starting point, could define a ground net

            By connected its meant that its connected by any element not being a current source. If there are parts of circuit which aren't
            connected in that sense, there wouldn't be one uniq solution, because there could be any voltage difference between disconnected 
            parts of netlist.

            Return: dictionary of disconnected nets from ground
        """
        not_connected_nets = {}
        for net in connected_nets[0]:           
            for element in self.elements_on_net[net]:
                if isinstance(element,scs_elements.Element) and not isinstance(element,scs_elements.CurrentSource):
                    for net2 in element.nets[:2]:
                        if net2 not in connected_nets[0]: 
                            connected_nets[0].append(net2)
                elif isinstance(element,Instance):
                    if element.name not in connected_nets:
                        connected_nets.update({element.name:{0:inv_map(element.port_map)[net]}})
                    else:
                        updated = False
                        for subnet in inv_map(element.port_map)[net]:
                            if subnet not in connected_nets[element.name][0]:
                                connected_nets[element.name][0].append(subnet)
                                updated = True
                        if not updated: continue
                    ele_not_connected_nets = self.subinstances[element.name].nets_not_connected_to_gnd(connected_nets[element.name])
                    if ele_not_connected_nets:
                        not_connected_nets.update({element.name:ele_not_connected_nets})
                    elif element.name in not_connected_nets:
                        not_connected_nets.pop(element.name)
                    for port_net in element.port_map:
                        if port_net in connected_nets[element.name][0] and element.port_map[port_net] not in connected_nets[0]:
                            connected_nets[0].append(element.port_map[port_net])
                    
        for net in self.elements_on_net:
            if net not in connected_nets[0]:
                if 0 not in not_connected_nets:
                    not_connected_nets.update({0:[net]})
                else:
                    not_connected_nets[0].append(net)

        return not_connected_nets

    def check_path_to_gnd(self):
        """ Checks whether all nets have connection to ground
            
            By connected its meant that its connected by any element not being a current source. If there are parts of circuit which aren't
            connected in that sense, there wouldn't be one uniq solution, because there could be any voltage difference between disconnected 
            parts of netlist.
        
            return True or False             
        """
        not_connected_nets = self.nets_not_connected_to_gnd({0:['0']})
        if len(not_connected_nets): 
            logging.error("Nets without connection to gnd: %s" % self._flat_net_hier(not_connected_nets)[0])
        return False if len(not_connected_nets) else True 
           
    def _flat_net_hier(self,loops):
        """ Flattens hierachical structure for loops for better display to user
            
            loops: hierarchical dictionary 0                :   [list of instance nets with voltage sources in a loop]
                                           subinstance_name :   subinstance hierarchical dictionary

            Provide a flat list of loops derived from hierarchicla structure. Hierarchy will be note by a spice dot notation
        """
        flat_net_hier = []
        for name,loop in loops.items():
            if name:
                loop = self.subinstances[name]._flat_net_hier(loop)                
                for nets in loop:
                    flat_loops_nets =[]
                    for i in  range(len(nets)):
                        net ="%s.%s" % (name,nets[i])
                        if net not in flat_loops_nets:
                            flat_loops_nets.append(net)
                    if flat_loops_nets: flat_net_hier.append(flat_loops_nets)
            else:                 
                for nets in loops[0]: 
                    flat_loops_nets =[]                
                    for net in nets:
                        if net not in flat_loops_nets:
                            flat_loops_nets.append(net)
                    if flat_loops_nets: flat_net_hier.append(flat_loops_nets)
        return flat_net_hier
                
    def _loops_and_chained_ports(self):
        """ Provides loops nets hierarchical structure and connected ports dictionary

            Returns loops hierarchical dictionary and updates connected ports dictionary.
            It's used for checking wheter there are any voltage loops in circuit.           
        """
        loops = {0:[]}
        chains = []
        for subname,subinstance in self.subinstances.items():
            loops.update({subname:subinstance._loops_and_chained_ports()})
        
        used_nets = []
        for net,elements in self.elements_on_net.items():
            if net in used_nets: continue      
            used_nets.append(net)      
            chain = [net]
            tracked_elements = []
            loop_found = False 
            check_elements = copy.copy(elements)
                    
            for element in check_elements:
                if element in tracked_elements: continue
                else: tracked_elements.append(element)
                new_nets = []
                if isinstance(element,scs_elements.VoltageSource):
                    for chain_net in chain:
                        if chain_net in element.nets[:1]:
                            new_nets.append(element.nets[0] if element.nets[1] == net else element.nets[1])
                            break
                elif isinstance(element,Instance):
                    ports  = inv_map(element.port_map)[net] if net in inv_map(element.port_map) else []
                    for port in ports:
                        for chained_port in element.chained_ports[port]:
                            new_nets.append(element.port_map[chained_port])

    
                for new_net in new_nets:
                    if not new_net in chain:
                        chain.append(new_net)
                        used_nets.append(new_net)
                        if not new_net == net:
                            check_elements += self.elements_on_net[new_net]
                    else:
                        loop_found = True
                
            if loop_found: loops[0].append(chain)
            chains.append(chain)
        
        for port in self.port_nets:
            self.chained_ports.update({port:[]})
            for chain in chains:
                if port in chain:
                    for other_port in self.port_nets:
                        if not other_port == port and other_port in chain:
                            self.chained_ports[port].append(other_port)
                    break
        return loops                        
                                                      
    def check_voltage_loop(self):
        """ Checks whether there are any voltage source loops in circuit.

            Consistent or not voltage sources loops aren't allowed, and this check finds out
            whether there are any in circuit. Inconsistent voltage source loop cause circuit
            to not have any valid solution, and consistent voltage loops makes currents which
            goes through such loops to be undefinded.

            Returns True if its ok or False if not.
        """
        loops = self._loops_and_chained_ports()        
        loops = self._flat_net_hier(loops)
        if not loops:             return True  
        else:
            for loop in loops:
                logging.error("Voltage loop on nets: %s" % loop)
            return False

    def _prepare_nets(self):
        """
            Makes inner nets and port_nets list from elements_on_net dictionay

            It also updates a net_name_index dictionary which holds a number for each net
            It makes easy to keep track of what position on vector is the value refering to.
        """
        self.inner_nets = []
        self.port_nets = []        
        self.net_name_index = {}
        for net in self.elements_on_net:            
            if net in self.port_map: 
                self.port_nets.append(net)                
            elif (not net == '0') or (self.parent):
                self.inner_nets.append(net)
        
        self.nets = self.inner_nets + self.port_nets

        for i in range(len(self.nets)):
            self.net_name_index.update({self.nets[i]:i})
  
    def update_eq_with_vs(self,net,G_v,I,ignore_element = None):
        """ Tries to update system of equations for finding solution with voltage source equation.
                
            net: net for which we try to make a equation for, from theory number of equations needed to solve a
                circuit is same as number of nets
            G_v: conductance vector forming a equation, to be updated by this function
            I: current side of equation to be updated by this function
            ignore_element: element which will be ignore while looking for equation

            This procedure looks for unused voltage source to form another equation to system, on that net or if its a supernet
            (few nets connected by voltage source) walk on through of any nets of that super ne, and see if any voltage
            source wasn't used yet to form a equation. If no any such voltage source was found return false.
            If voltage source is found update the equation and return true.
        """
        updated = False
        for element in self.elements_on_net[net]:  
            if element is ignore_element: continue             
            if isinstance(element,scs_elements.VoltageSource) and (net in element.nets[:2]):
                if (not element in self.used_voltage_sources):
                    if element.nets[0] in self.net_name_index:G_v[self.net_name_index[element.nets[0]]] += 1
                    if element.nets[1] in self.net_name_index: G_v[self.net_name_index[element.nets[1]]] += -1  
                    if isinstance(element,scs_elements.VoltageControlledVoltageSource):
                        if element.nets[2] in self.net_name_index: G_v[self.net_name_index[element.nets[2]]] += -element.values[0]
                        if element.nets[3] in self.net_name_index: G_v[self.net_name_index[element.nets[3]]] += +element.values[0]
                    elif isinstance(element,scs_elements.CurrentControlledVoltageSource): 
                        if element.names[1] not in self.elements:
                            raise Exception("No such element %s referenced by %s" % (element.names[1],element.names[0]))
                        ref_element = self.elements[element.names[1]]
                        ref_net =ref_element.nets[0]            
                        r = element.values[0]
                        G_vx = [0 for i in range(len(self.nets))]
                        Ix = [0]
                        self.update_current_v(ref_element,ref_net,G_vx,Ix)
                        I[0] += Ix[0]*r
                        for i in range(len(G_v)): G_v[i] += r*G_vx[i]
                    else: I[0] += element.values[0]
                    self.used_voltage_sources.append(element)
                    updated = True
                    break
                else:
                    other_net = element.nets[0] if element.nets[1] == net else element.nets[1]
                    updated = self.update_eq_with_vs(other_net,G_v,I,element)                    
            elif isinstance(element,Instance):
                ports = inv_map(element.port_map)[net]
                for port in ports:
                    for subelement in element.elements_on_net[port]:
                        if isinstance(subelement,scs_elements.VoltageSource) and (port in subelement.nets[:2]):
                            if (not subelement in element.used_voltage_sources):
                                G_d,I_port = element.port_voltage(port,subelement)
                                for port_key,g in G_d.items(): # Renamed port to port_key
                                    if element.port_map[port_key] in self.net_name_index: G_v[self.net_name_index[element.port_map[port_key]]] += g # Renamed port to port_key
                                I[0] += I_port
                                element.used_voltage_sources.append(subelement)
                                updated = True
                                break
                            else:
                                G_i = [0 for i in range(len(element.nets))]
                                G_pd = {}                                
                                other_subnet = subelement.nets[0] if subelement.nets[1] == port else subelement.nets[1]
                                if element.update_eq_with_vs(other_subnet,G_i,I,subelement):                                    
                                    i = 0
                                    for port_net in self.port_nets:
                                        G_pd.update({port_net:G_pv[i]})
                                        i = i + 1
                                    for port_key,g in G_d.items(): # Renamed port to port_key
                                        if element.port_map[port_key] in self.net_name_index: G_v[self.net_name_index[element.port_map[port_key]]] += g # Renamed port to port_key
                                    updated = True
                    if updated: break
                if updated: break
        if not updated and net in self.port_map: 
            updadated = self.parent.update_eq_with_vs(self.port_map[net],G_v,I,self)
        return updated
    
    def solve(self):
        """ Solves the instance that is:

            V - node voltage vector
            V = [Vi ; Vp]
            Vi - inner nodes voltage
            Vp - port nodes vector
            Vi = Ap*Vp + V0
            Ap - linear function matrix (Attenuation matrix)
            V0 - inner nodes voltage vector for Vp = 0
    
            By solving instance we provide update Ap matrix and V0 vector.
            G * V = I
            [G_i, G+p] * [Vi ; Vp]  = I
            G_i*Vi + G_p*Vp = I
            
            Vi = -G_i^-1*G_p*Vp + G_i^-1*I
            Vi = Ap*Vp + V0
            
            Thus we update G matrix (write the equations), and by doing linear algebra we calculate the results.
            
        """
        for subname,subinstance in self.subinstances.items():
            subinstance.solve()       
        
        N = len(self.nets)
        Ni = len(self.inner_nets)
        Np = len(self.port_nets)
        for i in range(N):
            self.net_name_index.update({self.nets[i]:i})
    
        G_m = []
        I_v = []
        self.used_voltage_sources = []        

        for net in self.inner_nets:
            G_v = [0 for i in range(len(self.nets))]
            I = [0]
            if not self.update_eq_with_vs(net,G_v,I):
                for element in self.elements_on_net[net]:
                    self.update_current_v(element,net,G_v,I)
            #G_m.append(G_v)
            G_m.append([sympy.cancel(tmp) for tmp in G_v])
            I_v.append([sympy.cancel(tmp) for tmp in I])
            
        #Make and slice the Matrix G_M = [G_i | G_p]
        G_m = sympy.Matrix(G_m)
        I_v = sympy.Matrix(I_v)
        G_i = G_m[:,:Ni]
        G_p = G_m[:,Ni:]
                
        # G_i*V_i + G_p*V_p  = I_v
        # V_i = G_i^-1 I_v - G_i^-1 * G_p * V_p
        # V_i = Vo +Ap * vp
        try:
            G_i_inv = G_i.inv() 
        except ValueError as e:
            raise scs_errors.ScsElementError("%s is ill conditioned, and has no unique solution." % self.name if self.name else "TOP INSTANCE")
        self.V0_m = G_i_inv*I_v
        self.Ap_m = -G_i_inv*G_p

        #Translate those into dictionaries
        for i in range(Ni):
            self.V0.update({self.inner_nets[i]:self.V0_m[i]})
        
        for j in range(Np):
            tmp_dict = {}
            for i in range(Ni):
                tmp_dict.update({self.inner_nets[i]:self.Ap_m[i,j]})
            self.Ap.update({self.port_nets[j]:tmp_dict})
             
    def adjoint_elements(self,refelement,net):
        """ Provides list of pairs of element,net that are adjoint to reference element on provided net
            
            refelement: reference element
            net: name of the net where we search for adjoint element

            If net is part of supernet all nets in supernet will be search and be put on output. Returns list of pair [(element,net) ... ].
        """
        elements_nets = []
        for element in self.elements_on_net[net]:
            if not element is refelement:
                if isinstance(element,scs_elements.VoltageSource):
                    elements_nets = self.adjoint_elements(element,element.nets[0] if element.nets[1] == net else element.nets[1])
                else: elements_nets.append((element,element.nets[1] if element.nets[0] == net else element.nets[0]))
        return elements_nets
           
    def update_current_v(self,element,net,G_v,I):
        """ Updates conductance vector and current part of equation for net.

            element: element whos current will be added to eqution
            net: net for which we write the equation
            G_v: conductance vector to be updated by the element
            I: current to be updated by the element

            For passive elements it will be as current flowing out of the net. For current source,
            the other side of equation will be udateded so it will be current flowing into the net.
            
        """
        
        if isinstance(element,scs_elements.Element) and (net in element.nets[:2]):
            other_net  = element.nets[1] if (net == element.nets[0]) else element.nets[0]
            
            if isinstance(element,scs_elements.VoltageSource):                
                for other_net_element in self.elements_on_net[other_net]:
                    if not other_net_element is element: self.update_current_v(other_net_element,other_net,G_v,I)
            elif isinstance(element,scs_elements.PassiveElement):
                g = element.conductance()
                if net in self.net_name_index: G_v[self.net_name_index[net]] += g
                if other_net in self.net_name_index: G_v[self.net_name_index[other_net]] -= g
            elif isinstance(element,scs_elements.VoltageControlledCurrentSource):
                gm = (element.values[0] if element.nets[0] == net else -element.values[0])
                if element.nets[3] in self.net_name_index: G_v[self.net_name_index[element.nets[3]]] += gm
                if element.nets[2] in self.net_name_index: G_v[self.net_name_index[element.nets[2]]] -= gm   
            elif isinstance(element,scs_elements.CurrentControlledCurrentSource):         
                ref_element = self.elements[element.names[1]]
                ref_net =ref_element.nets[0]
                refelements_nets = [(ref_element,1)]
                if isinstance(ref_element,scs_elements.VoltageSource):
                    refelements_nets = self.adjoint_elements(ref_element,ref_net)                
                a = 0
                G_vx = [0 for i in range(len(self.nets))]
                Ix = [0]
                for ref_element,ref_net_item in refelements_nets: # Renamed ref_net to ref_net_item
                    if ref_element is element: a += (1 if ref_net_item == element.nets[0] else -1) # Renamed ref_net to ref_net_item
                    else: self.update_current_v(ref_element,ref_net_item,G_vx,Ix) # Renamed ref_net to ref_net_item
                a = 1 - a*element.values[0]
                if a: a = element.values[0]/a
                else: raise scs_errors.ScsInstanceError("Error: ill conditioned current controlled source")
               
                for i in range(len(G_vx)): G_v[i] += a*G_vx[i]
                I[0] += a*Ix[0]
            elif isinstance(element,scs_elements.CurrentSource):
                I[0] += (element.values[0] if element.nets[0] == net else -element.values[0])
        elif isinstance(element,Instance):
                port_nets = inv_map(element.port_map)[net]
                #Check if it is connected, if it is we need to take into account the chain voltage, not current
                for port_net in port_nets:
                    G_d,I_port,other_ports = element.port_current(port_net)
                    for port,g in G_d.items():
                        if element.port_map[port] in self.net_name_index: G_v[self.net_name_index[element.port_map[port]]] += g
                    I[0] += I_port
                    for other_port in other_ports:
                        for other_port_element in self.elements_on_net[element.port_map[other_port]]:
                            if not other_port_element is element: self.update_current_v(other_port_element,element.port_map[other_port],G_v,I)

    def current_v(self,element,net):
        """ Provide current thruogh element flowing out of the net.
    
            element: element for which we calculate the current
            net: net out of which current flows through a element.

            Return conductance vector and current scalar. So final current is Iout = G_v*V - I
        """
        G_v = [0 for i in range(len(self.nets))]
        I = [0]
        self.update_current_v(element,net,G_v,I)
        return G_v,I
                
    def port_voltage(self,port,element):
        """ Translate subinstance voltage sources equation as equation using port volages.
            
            port: net for which we write equation (name as in subinstance)
            element: voltage source for which we write equation

            While writing equations if net is a port of some subinstance (self), on which there is an unused voltage source
            (one which was unused while solving subinstance) we must use it to write it next equation. This function
            provides this equation in form of port voltages (uknown because parent instance is being solved), while we can
            use inner voltages which are in linear funciton of port voltages as well. This equation will be used to 
            write an equation using parent circuit net names. Returns conductance dictionary (not to confuse numbers with port nets).                
        """
        N = len(self.nets)
        Ni = len(self.inner_nets)
        Np = len(self.port_nets)
        
        G_v = [0 for i in range(N)]
        I = [0]
        G_v[self.net_name_index[element.nets[0]]] = 1
        G_v[self.net_name_index[element.nets[1]]] = -1  
        if isinstance(element,scs_elements.VoltageControlledVoltageSource):
            G_v[self.net_name_index[element.nets[2]]] = element.values[0]
            G_v[self.net_name_index[element.nets[3]]] = -element.values[0]                                   
        else: I = [element.values[0]]
        
        G_v1,G_v2 = G_v[:Ni],G_v[Ni:]
        G_v1m,G_v2m = sympy.Matrix(G_v1),sympy.Matrix(G_v2)
        
        if G_v1: 
            G_pv = list(self.Ap_m.transpose()*G_v1m+G_v2m)
            I[0] += list(G_v1m.transpose()*self.V0_m)[0]
        else: G_pv = list(G_v2m)
        

        #Translate vector into dictionary
        G_pd = {}
        i = 0
        for port_net in self.port_nets:
            G_pd.update({port_net:G_pv[i]})
            i = i + 1
        
        return G_pd,I[0]
                
    def port_current(self,port):
        """ Translate subinstance port current equation as equation using port voltages.
            
            port: net for which we write equation (name as in subinstance)

            Provides current from a port in form of:
            port_current I = G*Vp + I_other_ports
                            
            Returns:
            G_pd: conductance dictionary
            other_ports: list of other ports current through which we needs to add
        """
        N = len(self.nets)
        Ni = len(self.inner_nets)
        Np = len(self.port_nets)
        G_v = [0 for i in range(N)]
        I = [0]
        for element in self.elements_on_net[port]:
            self.update_current_v(element,port,G_v,I)
        
        G_v1,G_v2 = G_v[:Ni],G_v[Ni:]
        G_v1m,G_v2m = sympy.Matrix(G_v1),sympy.Matrix(G_v2)
        
        if G_v1: 
            G_pv = list(self.Ap_m.transpose()*G_v1m+G_v2m)
            I[0] += list(G_v1m.transpose()*self.V0_m)[0]
        else: G_pv = list(G_v2m)
        
        #Translate vector into dictionary
        G_pd = {}
        i = 0
        for port_net in self.port_nets:
            G_pd.update({port_net:G_pv[i]})
            i = i + 1
        
        return G_pd,I[0],self.chained_ports[port]

    def isub(self,port):
        """ Calculate current flowing into port
            
            port: port for which current will be calculated, can be written in dot notation

            Self needs to be solved to use it. Returns a value of this current. 
        """
        hier_port = port.split('.')
        if len(hier_port)<2:
            raise scs_errors.ScsInstanceError("Can't calculate port current from top circuit")
        elif len(hier_port)==2:
            subinstance_name = hier_port[-2]
            port_net = hier_port[-1]
            if subinstance_name not in self.subinstances: 
                raise scs_errors.ScsInstanceError("No %s subinstance in %s" %(subinstance_name,self.name if self.name else "TOP INSTANCE"))
            subinstance = self.subinstances[subinstance_name]
            if port_net not in subinstance.port_nets: 
                raise scs_errors.ScsInstanceError("No port %s in subinstance %s of %s" %(port_net,subinstance.name,self.name if self.name else "TOP INSTANCE"))
            G_v =[0 for i in range(len(self.nets))]
            I = [0]
            G_d,I[0],other_ports = subinstance.port_current(port_net)
            for p,g in G_d.items():
                if subinstance.port_map[p] in self.net_name_index: G_v[self.net_name_index[subinstance.port_map[p]]] += g 
            for other_port in other_ports:
                for other_port_element in self.elements_on_net[subinstance.port_map[other_port]]: # element was not defined, changed to subinstance
                    if not other_port_element is subinstance: self.update_current_v(other_port_element,subinstance.port_map[other_port],G_v,I) # element was not defined, changed to subinstance
            i = 0
            for g in G_v:
                if g:
                    I[0] += g*self.v(self.nets[i])
                i += 1
            return I[0]
            #return sympy.factor(I[0],sympy.symbols('s'))
            #return I[0].simplify()
            #return sympy.powsimp(I[0])
        else:        
            subinstance = self
            for subname in hier_port[:-2]:
                if subname in subinstance.subinstances:
                    subinstance = subinstance.subinstances[subname]
                else:
                    raise scs_errors.ScsInstanceError("No %s subinstance in %s" %(subname,self.name if self.name else "TOP INSTANCE")) # hier_name was not defined, changed to subname
            return subinstance.isub('%s.%s' % (hier_port[-2],hier_port[-1])) # hier_inst was not defined, changed to hier_port

    def i(self,instance):
        """ Current flowing through instance

            instance: instance for which we calculate current for, can be written in dot notation
            
            Returns value of a current. Instance need to be solved first to use it.
        """
        hier_inst = instance.split('.')
        
        if len(hier_inst) == 1:
            if hier_inst[0] in self.elements:
                G_v,I = self.current_v(self.elements[hier_inst[0]],self.elements[hier_inst[0]].nets[0])
                idx = 0 # i was not defined, changed to idx
                for g in G_v:
                    if g:
                        I[0] -= g*self.v(self.nets[idx]) # i was not defined, changed to idx
                    idx += 1 # i was not defined, changed to idx
                #return sympy.factor(I[0],sympy.symbols('s'))
                #return I[0].simplify()
                return -I[0]
            else: 
                raise scs_errors.ScsInstanceError("Can't find element %s in %s" % (hier_inst[0],self.name if self.name else "TOP INSTANCE"))
        else:
            subinstance = self
            for subname in hier_inst[:-1]:
                if subname in subinstance.subinstances:
                    subinstance = subinstance.subinstances[subname]
                else: 
                    raise scs_errors.ScsInstanceError("No %s subinstance in %s" %(subname,self.name if self.name else "TOP INSTANCE")) # hier_name was not defined, changed to subname
            return subinstance.i(hier_inst[-1])

    def v(self,net1,net2=None):
        """ Calculate voltage differnce between nets 1 and 2 V(net1)-V(net2)
            
            net1: 1st voltage net name, can be in dot notation

            net2: 2nd voltage net name, can be in dot notation
            
            Instance need to be solved to use this function.
        """
        hier_net_1 = net1.split('.') if net1 else None
        hier_net_2 = net2.split('.') if net2 else None

        v = []
        for hier_net in (hier_net_1,hier_net_2):
            if hier_net and len(hier_net) == 1 :
                net = hier_net[0]
                if not net in self.V:
                    if net in self.inner_nets:
                        vx = self.V0[net]
                       # Ap = self.Ap[net] if net in self.Ap else {}
                        for port,Ap_val in self.Ap.items(): # Renamed Ap to Ap_val
                            ap = Ap_val[net] # Renamed Ap to Ap_val
                            if ap:
                                if port not in self.Vp:
                                    self.Vp.update({port:self.parent.v(self.port_map[port])})                                        
                                vx += ap*self.Vp[port]
                        self.V.update({net:vx})
                    elif net in self.port_nets:
                        if net not in self.Vp:
                            self.Vp.update({net:self.parent.v(self.port_map[net])})
                        self.V.update({net:self.Vp[net]})
                    else:
                        if net == '0' and not self.parent:
                            self.V.update({'0':0})
                        else: 
                            raise scs_errors.ScsInstanceError("No net %s in %s" %(net,self.name if self.name else "TOP INSTANCE"))
                v.append(self.V[net])        
            elif hier_net:
                hier_instance = self    
                for hier_name in hier_net[:-1]:
                    if hier_name in hier_instance.subinstances:
                        hier_instance = hier_instance.subinstances[hier_name]
                    else:
                        raise scs_errors.ScsInstanceError("No %s subinstance in %s" %(hier_name,self.name if self.name else "TOP INSTANCE"))
                v.append(hier_instance.v(hier_net[-1]))
            else:
                v.append(0)            
        #return sympy.factor(v[0]-v[1],sympy.symbols('s'))
        #return (v[0]-v[1]).simplify()                                      
        return v[0]-v[1]
        #return sympy.cancel(v[0]-v[1])
def _contract_chains(chains):
    """ Contracts chains in list into larger chains if are connected

        chains: list of chains that could be contracted
        
        Returns list of contracted chains. Connected chains are chains which both contain at least one of the net. 
        If 2 chains in chains are [[foo bar] [bar spam becon]] there will be contracted into [[ foo bar spam bacon]]

    """
    N = len(chains)
    contract_chains = []
    for i in range(N):
        joined = False
        for j in range(i+1,N):                
            for k in range(len(chains[i])):
                if chains[i][k] in chains[j]:
                    chains[j] += chains[i][:k] + chains[i][(k+1):]
                    joined = True
                    break  
        if not joined:
            contract_chains.append(chains[i])                 
    return contract_chains

def _is_a_loop(chain):
    """ Check if a chain is a loop
        
        chain: chain to be checked
    
        chain is a loop if there are at least to nets on its list with same name
        [spam spam baco] is a loop
        [spam bacon eggs] is not a loop
        
        Returns True or False
    """

    is_loop = False
    for i in range(len(chain)):
        if (chain[i] in chain[i+1:]):
            is_loop = True
            break
    return is_loop
        
def inv_map(map):
    """ Inverts a dictionary (map)
        
        map: dictionary to be inverted

        Exchanges key and values pair in dictionary with each other. If we got dictionary like
        { for: spam,
          bar: spam}
        The result of inversion will be dictionary:        
        { spam: [foo,bar]}

        Thus the values of result dictionary are in form of a list cause it could happen that original dictionary isn't one-to-one.
    """
    imap = {}
    for k, v in map_dict.items(): # Renamed map to map_dict
        if v in imap:
           imap[v].append(k)
        else:
            imap.update({v:[k]}) 
    return imap 
        
def getSubcircuit(name,circuit):
    """ Get subcircuit definition by a name from a dictionary.

        name: name of subcircuit to get
        
        circuit: circuit of which dictionary of subcircuits will be searched for subcircuit name

        If the circuit name isn't in the circuit dictionary, parent (if exists) will be search as well.
        Returns said subcircuit or None if there isn't any with such name.
    """
    if name in circuit.subcircuitsd:
        return circuit.subcircuitsd[name]
    elif circuit.parent:
        return getSubcircuit(name,circuit.parent)
    else: 
        return None

def make_top_instance(circuit):
    """ Makes top instance from circuit
        
        circuit: a circuit which will be instantiated

        Top circuit won't have a name or parent.
        Returns instance of a circuit or None if some error does appear.
    """
    try:
        return make_instance(None,None,circuit)
    except scs_errors.ScsInstanceError as e:
        logging.error(e)
        return None

def make_instance(parent,name,circuit,port_map={},passed_paramsd={}):
    """ Makes an instance of a circuit

        parent: parent of an instance (instance will be a subinstance of that parent
        
        name: a name string for new instance

        circuit: circuit which will be instantiated

        port_map: dictionary of instance_net:parent_net pairs

        passed_paramsd: parameters that are being passed to subinstance while instantiating it

        Makes a subinstance of a parent. Passed paramsd will be evaluated first, and then overwrite the default ones.
        Returns instance of a circuit or None if some error does apper.
    """
    inst = Instance(parent,name,port_map)
    try:
        inst.paramsd = scs_parser.evaluate_params(circuit.parametersd,parent)
    except scs_errors.ScsParameterError as e:
        raise scs_errors.ScsInstanceError("Error evaluating parametrs in %s subcircuit. %s" % (circuit.name,e))
    inst.paramsd.update(passed_paramsd)
    for ename,element in circuit.elementsd.items():
        if ename[0] in ['x','X']:   
            subcir_name = element.paramsl[-1]        
            
            subcircuit = getSubcircuit(subcir_name,circuit)       
            if subcircuit:
                subcir_portl = element.paramsl[:-1] 
                portmap = {}
                if  len(subcir_portl) == len(subcircuit.ports):
                    for i in range(len(subcir_portl)):
                        portmap.update({subcircuit.ports[i]:subcir_portl[i]})
                else:
                    raise scs_errors.ScsInstanceError("Error: subcircuit port lenght: %d != instance port length: %d \n Instance %s of subcircuit %s in %s subcircuit"
                                           % (len(subcircuit.ports),len(subcir_portl),ename,subcir_name,name if name else 'top'))
                try:                    
                    eps = scs_parser.evaluate_passed_params(element.paramsd,inst,{})
                except scs_errors.ScsParameterError as e:
                    raise scs_errors.ScsInstanceError("Error evaluating parametrs for instance: %s in %s subcircuit. %s" % (subcir_name,circuit.name,e))                    
                
                sub_inst = make_instance(inst,ename,subcircuit,portmap,eps)
                inst.add_sub_instance(sub_inst)
            else:
                raise scs_errors.ScsInstanceError("Error: no subcircuit definition of: %s found for instance %s in %s subcircuit"
                                        %(subcir_name, ename, circuit.name)) 
        elif ename[0] in scs_elements.elementd:
            try:
                inst.add_element(scs_elements.elementd[ename[0]](ename,element,inst.paramsd,parent))
            except (scs_errors.ScsParameterError,scs_errors.ScsElementError) as e:
                raise scs_errors.ScsInstanceError("Error evaluating parametrs for instance: %s in %s subcircuit. %s" % (ename,circuit.name,e))

        else:
            raise scs_errors.ScsInstanceError("Error: no element of that type: %s. Strange should have been cought by parser?"   
                  % (ename))
    inst._prepare_nets()
    return inst            

            