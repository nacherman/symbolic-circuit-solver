# spice_parser.py
import sympy as sp
from symbolic_components import (
    Resistor, Capacitor, Inductor,
    VoltageSource, CurrentSource,
    VCVS, VCCS, CCVS, CCCS,
    omega as omega_sym # Global omega from symbolic_components
)
import re

SUFFIX_LOOKUP = {
    'F': 1E-15, 'P': 1E-12, 'N': 1E-9, 'U': 1E-6, 'M': 1E-3,
    'K': 1E3, 'MEG': 1E6, 'G': 1E9, 'T': 1E12
}

def parse_value(value_str):
    original_value_str = value_str.strip()
    val_upper = original_value_str.upper()

    for suffix_key in sorted(SUFFIX_LOOKUP.keys(), key=len, reverse=True):
        if val_upper.endswith(suffix_key):
            num_part_str = original_value_str[:-len(suffix_key)]
            try:
                if num_part_str:
                    val = float(num_part_str) * SUFFIX_LOOKUP[suffix_key]
                    return val
            except ValueError:
                pass

    cleaned_str_for_unit_strip = original_value_str
    units_to_strip = ['FARAD', 'HENRY', 'OHMS', 'OHM', 'VOLTS', 'AMPS', 'HZ', 'DEG', 'RAD', 'S', 'F', 'H', 'V', 'A']
    units_to_strip.sort(key=len, reverse=True)

    for unit in units_to_strip:
        if cleaned_str_for_unit_strip.upper().endswith(unit.upper()):
            temp_cleaned_str = cleaned_str_for_unit_strip[:-len(unit)]
            if temp_cleaned_str:
                return parse_value(temp_cleaned_str)
            else:
                return original_value_str

    try:
        return float(original_value_str)
    except ValueError:
        return original_value_str

def get_sym_or_val(val_str_parsed, name_hint="val"):
    is_num_like = False
    num_val = None
    if isinstance(val_str_parsed, (float, int)):
        is_num_like = True
        num_val = val_str_parsed
    elif isinstance(val_str_parsed, str):
        try:
            num_val = float(val_str_parsed)
            is_num_like = True
        except ValueError:
            is_num_like = False

    if is_num_like:
        return num_val # Return as Python float/int
    else:
        # If it's a string that's not purely numerical, treat as symbol
        # Check if it already contains symbolic operators, then parse with sympify
        if any(op in str(val_str_parsed) for op in ['*', '/', '+', '-', '(', ')']):
            try:
                return sp.sympify(str(val_str_parsed), locals={'I': sp.I, 'pi': sp.pi, 'exp':sp.exp, 'omega':omega_sym})
            except (sp.SympifyError, TypeError):
                pass # Fallback to creating a simple symbol if sympify fails
        return sp.Symbol(str(val_str_parsed))


def parse_netlist(netlist_string):
    components = []
    active_omega = omega_sym

    lines = netlist_string.strip().split('\n')

    for line_num, original_line_with_comment in enumerate(lines):
        line_no_comment = original_line_with_comment.split(';', 1)[0]
        line_no_comment = line_no_comment.split('*', 1)[0]
        line = line_no_comment.strip()

        if not line : continue

        parts_preserved_case = line.split()
        parts_upper = line.upper().split()

        if not parts_upper: continue

        comp_name_preserved = parts_preserved_case[0]
        if not comp_name_preserved: continue
        comp_type_char = comp_name_preserved[0].upper()

        try:
            if comp_type_char == 'R':
                if len(parts_upper) < 4: raise ValueError("Resistor definition too short.")
                name, n1, n2, val_str = comp_name_preserved, parts_preserved_case[1], parts_preserved_case[2], parts_preserved_case[3]
                val = parse_value(val_str)
                r_sym_val = get_sym_or_val(val, name+"_val")
                components.append(Resistor(name, n1, n2, resistance_sym=r_sym_val))

            elif comp_type_char == 'L':
                if len(parts_upper) < 4: raise ValueError("Inductor definition too short.")
                name, n1, n2, val_str = comp_name_preserved, parts_preserved_case[1], parts_preserved_case[2], parts_preserved_case[3]
                val = parse_value(val_str)
                l_sym_val = get_sym_or_val(val, name+"_val")
                components.append(Inductor(name, n1, n2, inductance_sym=l_sym_val))

            elif comp_type_char == 'C':
                if len(parts_upper) < 4: raise ValueError("Capacitor definition too short.")
                name, n1, n2, val_str = comp_name_preserved, parts_preserved_case[1], parts_preserved_case[2], parts_preserved_case[3]
                val = parse_value(val_str)
                c_sym_val = get_sym_or_val(val, name+"_val")
                components.append(Capacitor(name, n1, n2, capacitance_sym=c_sym_val))

            elif comp_type_char == 'V' or comp_type_char == 'I':
                if len(parts_upper) < 3: raise ValueError(f"{comp_type_char} source definition needs at least name, n1, n2.")
                name, n1, n2 = comp_name_preserved, parts_preserved_case[1], parts_preserved_case[2]

                dc_val = None; ac_mag = None; ac_phase_rad = 0

                # Scan parts after nodes for keywords or direct value
                idx = 3
                source_value_parts = parts_preserved_case[idx:]
                source_value_parts_upper = parts_upper[idx:]

                parsed_keywords = False

                # Check for SIN(...) first using regex on the relevant part of original case line
                line_suffix = " ".join(parts_preserved_case[idx:])
                sin_match = re.search(r'SIN\s*\(([^)]+)\)', line_suffix, re.IGNORECASE)

                if sin_match:
                    parsed_keywords = True
                    sin_params_text = sin_match.group(1)
                    sin_params = [p.strip() for p in re.split(r'[\s,]+', sin_params_text) if p.strip()]
                    if len(sin_params) >= 2: # VOFF VAMPL ...
                        if dc_val is None: dc_val = parse_value(sin_params[0]) # VOFF
                        if ac_mag is None: ac_mag = parse_value(sin_params[1]) # VAMPL
                    if len(sin_params) >= 6: # ... PHASE_DEG is 6th param (index 5)
                        ac_phase_deg_sin = parse_value(sin_params[5])
                        if isinstance(ac_phase_deg_sin, (float, int)): ac_phase_rad = ac_phase_deg_sin * sp.pi / 180
                    elif ac_mag is not None and ac_phase_rad == 0: pass # Keep default 0 if phase not specified
                else:
                    # If not SIN(...) or SIN keyword not first, parse for DC/AC keywords
                    temp_idx_keywords = 0
                    while temp_idx_keywords < len(source_value_parts_upper):
                        keyword = source_value_parts_upper[temp_idx_keywords]
                        if keyword == 'DC':
                            parsed_keywords = True
                            if temp_idx_keywords + 1 < len(source_value_parts):
                                dc_val = parse_value(source_value_parts[temp_idx_keywords+1]); temp_idx_keywords += 2
                            else: raise ValueError(f"DC value missing for {name}.")
                        elif keyword == 'AC':
                            parsed_keywords = True
                            if temp_idx_keywords + 2 < len(source_value_parts):
                                ac_mag = parse_value(source_value_parts[temp_idx_keywords+1])
                                ac_phase_deg = parse_value(source_value_parts[temp_idx_keywords+2])
                                ac_phase_rad = ac_phase_deg * sp.pi / 180 if isinstance(ac_phase_deg, (float, int)) else 0
                                temp_idx_keywords += 3
                            else: raise ValueError(f"AC mag/phase missing for {name}.")
                        else:
                            # If it's not a recognized keyword, it might be a direct value if no keywords parsed yet
                            if not parsed_keywords and temp_idx_keywords == 0 and len(source_value_parts) > 0:
                                dc_val = parse_value(source_value_parts[0]) # Assume direct value is DC
                                parsed_keywords = True # Mark that we've taken a value
                                temp_idx_keywords +=1 # Move to next part
                            elif parsed_keywords : # If keywords were already parsed, this is extra
                                print(f"Warning: Extra/unhandled parameter '{source_value_parts[temp_idx_keywords]}' for source {name}.")
                                temp_idx_keywords +=1
                            else: # Unrecognized first parameter
                                temp_idx_keywords +=1


                val_to_use = None
                if ac_mag is not None:
                    val_to_use = ac_mag * sp.exp(sp.I * ac_phase_rad)
                elif dc_val is not None:
                    val_to_use = dc_val
                elif len(parts_upper) == 3 : # Only Name N+ N- given
                     val_to_use = 0; print(f"Warning: No value for source {name}, defaulting to 0.")
                else: # Some parameters but none successfully parsed as value
                    val_to_use = str(parts_preserved_case[3]) # Fallback to first value as potential symbol
                    print(f"Warning: Could not parse explicit DC/AC for {name}, using '{val_to_use}' as potential symbolic value.")


                final_value_sym = get_sym_or_val(val_to_use, name+"_val")

                if comp_type_char == 'V': components.append(VoltageSource(name, n1, n2, voltage_val_sym=final_value_sym))
                else: components.append(CurrentSource(name, n1, n2, current_val_sym=final_value_sym))

            elif comp_type_char == 'E':
                if len(parts_upper) < 6: raise ValueError("VCVS definition too short.")
                name,n1,n2,cp,cn,gain_str = parts_preserved_case[0],parts_preserved_case[1],parts_preserved_case[2],parts_preserved_case[3],parts_preserved_case[4],parts_preserved_case[5]
                gain = parse_value(gain_str); gain_s = get_sym_or_val(gain, name+"_gain")
                components.append(VCVS(name, n1, n2, cp, cn, gain_sym=gain_s))

            elif comp_type_char == 'G':
                if len(parts_upper) < 6: raise ValueError("VCCS definition too short.")
                name,n1,n2,cp,cn,gm_str = parts_preserved_case[0],parts_preserved_case[1],parts_preserved_case[2],parts_preserved_case[3],parts_preserved_case[4],parts_preserved_case[5]
                gm = parse_value(gm_str); gm_s = get_sym_or_val(gm, name+"_gm")
                components.append(VCCS(name, n1, n2, cp, cn, transconductance_sym=gm_s))

            elif comp_type_char == 'H':
                if len(parts_upper) < 5: raise ValueError("CCVS definition too short.")
                name,n1,n2,ctrl_comp_name,rm_str = parts_preserved_case[0],parts_preserved_case[1],parts_preserved_case[2],parts_preserved_case[3],parts_preserved_case[4]
                rm = parse_value(rm_str); rm_s = get_sym_or_val(rm, name+"_rm")
                components.append(CCVS(name, n1, n2, ctrl_comp_name, transresistance_sym=rm_s))

            elif comp_type_char == 'F':
                if len(parts_upper) < 5: raise ValueError("CCCS definition too short.")
                name,n1,n2,ctrl_comp_name,gain_str = parts_preserved_case[0],parts_preserved_case[1],parts_preserved_case[2],parts_preserved_case[3],parts_preserved_case[4]
                gain = parse_value(gain_str); gain_s = get_sym_or_val(gain, name+"_gain")
                components.append(CCCS(name, n1, n2, ctrl_comp_name, gain_sym=gain_s))

            elif parts_upper[0] == '.AC':
                if len(parts_upper) >= 3 and parts_upper[1] == 'OMEGA':
                    omega_val_str = parts_preserved_case[2]
                    parsed_omega_val = parse_value(omega_val_str)
                    if isinstance(parsed_omega_val, (float, int)):
                        active_omega = parsed_omega_val
                        print(f"Info: Parsed .AC OMEGA, using omega = {active_omega}")
                    else:
                        active_omega = sp.Symbol(str(parsed_omega_val))
                        print(f"Info: Parsed .AC OMEGA, using symbolic omega = {active_omega}")
            elif parts_upper[0].startswith('.'):
                print(f"Info: Ignoring dot command: {original_line}")
            else:
                print(f"Warning: Unknown component or command type: {original_line}")
        except ValueError as e:
            print(f"Error parsing line {line_num+1}: '{original_line}'. Error: {e}")
        except Exception as e:
            print(f"Unexpected error parsing line {line_num+1}: '{original_line}'. Error: {e}")
    return components, active_omega

if __name__ == '__main__':
    sample_netlist = """
    * Example Netlist for Parser
    R1 N1 N2 1K
    R2 N2 0 2kohm ; Resistor with unit
    C1 N2 N3 10uF
    L1 N3 0 5MH
    VS1 N1 0 DC 10 AC 5 0
    VS2 N4 0 20V
    IS1 N3 N2 AC 2MA 90 DC 0.1A
    IS2 N5 0 1A
    E1 N_EOUT 0 N2 N3 2.5
    G1 N_GOUT 0 N2 N3 0.1
    H1 N_HOUT 0 R2 100
    F1 N_FOUT 0 R2 50
    RX N_SYM N_SYM_GND MyResistanceSymbol
    VY N_V_SYM 0 MyVoltageSymbol
    VSIN_TEST N_SIN_T 0 SIN(0 5V 1KHZ 0 0 0DEG)
    VSIN2 N_SIN2 0 SIN(1 2 500 0 0 30)
    VSIN3 N_SIN3 0 SIN(1V 2V 1KHZ 1MS 1NS 45DEG)
    .AC OMEGA 1000
    * End of netlist
    """
    print("--- Parsing Netlist ---")
    parsed_components, final_omega = parse_netlist(sample_netlist)
    print(f"\n--- Parsed Components ({len(parsed_components)}) ---")
    for comp in parsed_components:
        print(f"  {comp.name} ({comp.__class__.__name__}): Nodes='{comp.node1}','{comp.node2}'")
        if hasattr(comp, 'control_node_p_name'):
            print(f"    Control Nodes: '{comp.control_node_p_name}','{comp.control_node_n_name}'")
        if hasattr(comp, 'control_current_comp_name'):
            print(f"    Control Component: '{comp.control_current_comp_name}' -> Uses symbol '{comp.I_control_sym}'")
        print("    Values:")
        for key, val in comp.values.items():
            val_str = ""
            is_sympy_num_like = hasattr(val, 'evalf') and not (hasattr(val, 'free_symbols') and val.free_symbols)
            is_sympy_expr_like = isinstance(val, (sp.Expr, sp.Symbol))

            if is_sympy_num_like : val_str = str(val.evalf(chop=True))
            elif is_sympy_expr_like and key == 'control_voltage_diff_expr' and hasattr(val, 'free_symbols'):
                val_str = sp.pretty(val)
            elif is_sympy_expr_like: val_str = str(val)
            else: val_str = str(val)
            print(f"      {key}: {val_str}")

    print(f"\nEffective Omega for AC analysis: {final_omega} (type: {type(final_omega)})")
    print("\n--- Testing parse_value ---")
    test_values = ["10k", "10K", "1m", "1u", "1n", "1p", "1f", "1.5MEG", "2G", "3T", "100",
                   "MySymbol", "10UF", "0.5mH", "10V", "2KOHMS", "10MV", "1F", "1FF", "1kHZ"]
    for tv in test_values:
        parsed = parse_value(tv)
        print(f"parse_value('{tv}') = {parsed} (type: {type(parsed)})")
