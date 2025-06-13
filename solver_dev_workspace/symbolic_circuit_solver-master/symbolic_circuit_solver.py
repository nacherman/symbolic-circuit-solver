import scs_parser
import scs_instance_hier
import scs_circuit
import logging

logging.basicConfig()
stderrLogger=logging.StreamHandler()
logging.getLogger().addHandler(stderrLogger)

#print parse_param_expresion('3.1+(2+x)+1k**20e-1')
top_cir = scs_parser.parse_file('test.sp', scs_circuit.TopCircuit())
#print evaluate_params(top_cir.parametersd)
top_instance = scs_instance_hier.make_top_instance(top_cir)
#top_instance.check_path_to_gnd()
#top_instance.check_voltage_loop()
#top_instance.check_current_singularities()
#print top_instance.solve()
top_instance.check_path_to_gnd()
top_instance.check_voltage_loop()
#print "end"
top_instance.solve()
print "Solved"

top_cir.perform_analysis(top_instance,'test')

#print top_instance.v('x1.c')
#print top_instance.i('x1.r1')
#print top_instance.isub('x1.b')
#total_p = 0
#for element in top_instance.elements:
#    I =top_instance.current(element)
#    U = top_instance.voltage(element)
#    P = top_instance.power(element)
#    total_p += P
#    print element.names[0]
#    print "Current: "+str(I)
#    print "Voltage: "+str(U)
#    print "Power: "+str(P)
#print "Total power: " +str(factor(total_p))
#if top_instance:
#    for ele in top_instance.elements: print ele.names,ele.nets,ele.values
