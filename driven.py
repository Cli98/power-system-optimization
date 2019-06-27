#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Apr  2 17:01:52 2019
Referrence: Tutorial code from Edgar Bahilo Rodríguez
@author: changlinli

"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
#import gurobipy
import pyomo.environ
from pyomo.environ import ConcreteModel,AbstractModel,Param,RangeSet,Set,BuildAction,Var,Objective,Piecewise,minimize,value
from pyomo.environ import NonNegativeReals,Integers,Binary,PositiveIntegers
from pyomo.opt import SolverStatus,TerminationCondition
from pyomo.opt import SolverFactory
from support import *
#%% take care of input data
machine = pd.read_excel(r"system load.xlsx")
cost_para = pd.read_excel(r"cost parameter.xlsx")
cost_para["Product_cost_ini"] = cost_para['a']+ cost_para['b']*machine["Pmin"]+cost_para['c']*machine["Pmin"]**2
load = pd.read_excel(r"load.xlsx")
#%% create absmodel
amodel = AbstractModel() 
amodel.generator = Set(initialize = machine["Units"])
amodel.nperiods = Param(within=PositiveIntegers,initialize = len(load))
amodel.periods = RangeSet(1,amodel.nperiods)
amodel.demand = Param(amodel.periods,within=NonNegativeReals,initialize=modifyind(load['demand']))
amodel.reserve = Param(amodel.periods,within=NonNegativeReals,default=0.0,initialize=modifyind(load['demand']*0.1))
amodel.minout = Param(amodel.generator,within=NonNegativeReals,default=0.0,initialize=modifyind(machine["Pmin"]))
amodel.maxout = Param(amodel.generator,within=NonNegativeReals,validate=check_max_power,initialize=modifyind(machine["Pmax"]))
amodel.RampUpLimit = Param(amodel.generator, within=NonNegativeReals,default=0.0,initialize=0.0)
amodel.RampDownLimit = Param(amodel.generator, within=NonNegativeReals,default=0.0,initialize=0.0)
amodel.SURampUpLimit = Param(amodel.generator, within=NonNegativeReals,validate = check_g_min_power,default=0.0,initialize=modifyind(machine["Pmin"]))
amodel.SDRampDownLimit = Param(amodel.generator, within=NonNegativeReals, validate = check_g_min_power,default=0.0,initialize=modifyind(machine["Pmin"]))
amodel.minUpTime = Param(amodel.generator, within=NonNegativeReals,initialize=modifyind(machine["minUpTime"]),mutable=True)
amodel.minDownTime = Param(amodel.generator, within=NonNegativeReals,initialize=modifyind(machine["minDownTime"]),mutable=True)
#%% create state
amodel.K0State = Param(amodel.generator, within=Integers, validate=check_inistage,initialize=modifyind(machine['inistate']))
amodel.K0On = Param(amodel.generator, within=Binary, initialize=check_inistageon)
amodel.geninion = Param(amodel.generator, within=NonNegativeReals,initialize = enforce_inistageon)
amodel.geninioff = Param(amodel.generator, within=NonNegativeReals,initialize = enforce_inistageoff)

#%% generation cost function
amodel.pgenK0 = Param(amodel.generator, within=NonNegativeReals,initialize=modifyind(machine["Pmin"]))
amodel.PCost0 = Param(amodel.generator, within=NonNegativeReals,initialize=modifyind(cost_para["a"]))
amodel.PCost1 = Param(amodel.generator, within=NonNegativeReals,initialize=modifyind(cost_para["b"])) 
amodel.PCost2 = Param(amodel.generator, within=NonNegativeReals,initialize=modifyind(cost_para["c"]))
amodel.numcurve = Param(within=PositiveIntegers,default=3,initialize=4)
def gen_piecewise_curve(amodel,g,t):
    min_power = value(amodel.minout[g])
    max_power = value(amodel.maxout[g])
    n = value(amodel.numcurve)
    width = (max_power - min_power) / float(n)
    amodel.createpoints[g, t] = [min_power + i*width for i in range(0,n+1)]
amodel.createpoints = {}
amodel.CreatePowerGenerationPiecewisePoints = BuildAction(amodel.generator * amodel.periods, rule=gen_piecewise_curve)
amodel.ShutdownCostCoefficient = Param(amodel.generator, within=NonNegativeReals, default=0.0,initialize=0.0)
amodel.hc = Param(amodel.generator, within=NonNegativeReals, default=0.0,initialize=modifyind(cost_para["hc"]))
amodel.cc = Param(amodel.generator, within=NonNegativeReals, default=0.0,initialize=modifyind(cost_para["cc"]))
amodel.t_cold = Param(amodel.generator, within=NonNegativeReals, default=0.0,initialize=modifyind(cost_para["t_cold"]))

#%% vars
#result of interest: UnitOn+PowerGenerated
amodel.UnitOn = Var(amodel.generator, amodel.periods, within=Binary,initialize=0.0)
amodel.PowerGenerated = Var(amodel.generator, amodel.periods, within=NonNegativeReals,initialize=0.0)
amodel.MaximumPowerAvailable = Var(amodel.generator, amodel.periods, within=NonNegativeReals,initialize=0.0)

amodel.ProductionCost = Var(amodel.generator, amodel.periods, within=NonNegativeReals,initialize = 0.0,bounds=bounds_rule)#modifyind(cost_para["Product_cost_ini"])
amodel.StartupCost = Var(amodel.generator, amodel.periods, within=NonNegativeReals,initialize=0.0)
amodel.ShutdownCost = Var(amodel.generator, amodel.periods, within=NonNegativeReals,initialize=0.0)

amodel.TotalProductionCost = Var(within=NonNegativeReals,initialize=0.0)
amodel.TotalFixedCost = Var(within=NonNegativeReals,initialize=0.0)

amodel.ProductionEqualsDemand = Constraint(amodel.periods, rule=production_equals_demand_rule)
amodel.EnforceReserveRequirements = Constraint(amodel.periods, rule=enforce_reserve_requirements_rule)

amodel.EnforceGeneratorOutputLimitsPartA = Constraint(amodel.generator, amodel.periods, rule=enforce_generator_output_limits_rule_part_a)
amodel.EnforceGeneratorOutputLimitsPartB = Constraint(amodel.generator, amodel.periods, rule=enforce_generator_output_limits_rule_part_b)
amodel.EnforceGeneratorOutputLimitsPartC = Constraint(amodel.generator, amodel.periods, rule=enforce_generator_output_limits_rule_part_c)

#amodel.EnforceMaxAvailableRampUpRates = Constraint(amodel.generator, amodel.periods, rule=enforce_max_available_ramp_up_rates_rule)
#amodel.EnforceMaxAvailableRampDownRates = Constraint(amodel.generator, amodel.periods, rule=enforce_max_available_ramp_down_rates_rule)
amodel.ComputeProductionCosts = Piecewise(amodel.generator * amodel.periods, amodel.PowerGenerated, amodel.ProductionCost, pw_pts=amodel.createpoints, f_rule=production_cost_function, pw_constr_type='UB')
#amodel.ComputeProductionCosts = Constraint(amodel.generator, amodel.periods, rule=production_cost_function)

#%% total cost
amodel.ComputeTotalProductionCost = Constraint(rule=compute_total_production_cost_rule)
amodel.ComputeShutdownCosts = Constraint(amodel.generator, amodel.periods, rule=compute_shutdown_costs_rule)
amodel.ComputeStartupCosts = Constraint(amodel.generator, amodel.periods, rule=compute_startup_costs_rule)
amodel.ComputeTotalFixedCost = Constraint(rule=compute_total_fixed_cost_rule)
amodel.EnforceUpTimeConstraintsInitial = Constraint(amodel.generator, rule=enforce_up_time_constraints_initial)
amodel.EnforceUpTimeConstraintsSubsequent = Constraint(amodel.generator, amodel.periods, rule=enforce_up_time_constraints_subsequent)
amodel.EnforceDownTimeConstraintsInitial = Constraint(amodel.generator, rule=enforce_down_time_constraints_initial)
amodel.EnforceDownTimeConstraintsSubsequent = Constraint(amodel.generator, amodel.periods, rule=enforce_down_time_constraints_subsequent)
amodel.TotalCostObjective = Objective(rule=total_cost_objective_rule, sense=minimize)

#%% compile
instance = amodel.create_instance()
from pyomo.util.infeasible import log_infeasible_constraints
#instance.pprint()
opt = SolverFactory("gurobi", solver_io="python")
results = opt.solve(instance, tee=True, keepfiles=False)
log_infeasible_constraints(instance)
#, options_string="mip_tolerances_integrality=1e-9 mip_tolerances_mipgap=0"




for v in instance.component_objects(Var, active=True):
    print ("Variable component object",v)
    print ("Type of component object: ", str(type(v))[1:-1]) # Stripping <> for nbconvert
    varobject = getattr(instance, str(v))
    print ("Type of object accessed via getattr: ", str(type(varobject))[1:-1])
    for index in varobject:
        print ("   ", index, varobject[index].value)
