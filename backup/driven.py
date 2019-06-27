#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Apr  2 17:01:52 2019

@author: changlinli
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pyomo.environ import AbstractModel,Param,RangeSet,Set,BuildAction,Constraint,Var,Objective
from pyomo.environ import NonNegativeReals,Integers,Binary,PositiveIntegers
from pyomo.opt import SolverStatus,TerminationCondition
from pyomo.opt import SolverFactory
from support import *
#%% take care of input data
pd.read_excel()
#%% create absmodel
amodel = AbstractModel()
amodel.generator = Set()
amodel.nperiods = Param(within=PositiveIntegers)
amodel.periods = RangeSet(1,amodel.nperiods)
amodel.demand = Param(amodel.nperiods,within=NonNegativeReals,default=0.0)
amodel.reserve = Param(amodel.nperiods,within=NonNegativeReals,default=0.0)
amodel.minout = Param(amodel.generator,within=NonNegativeReals,default=0.0)
amodel.maxout = Param(amodel.generator,within=NonNegativeReals,validate=check_max_power)
amodel.RampUpLimit = Param(amodel.generator, within=NonNegativeReals)
amodel.RampDownLimit = Param(amodel.generator, within=NonNegativeReals)
amodel.SURampUpLimit = Param(amodel.generator, within=NonNegativeReals,validate = check_g_min_power)
amodel.SDRampDownLimit = Param(amodel.generator, within=NonNegativeReals, validate = check_g_min_power)
amodel.minUpTime = Param(amodel.generator, within=NonNegativeReals)
amodel.minDownTime = Param(amodel.generator, within=NonNegativeReals)
#%% create state
amodel.K0State = Param(amodel.generator, within=Integers, validate=check_inistage)
amodel.K0On = Param(amodel.generator, within=Binary, initialize=check_inistageon)
amodel.geninion = Param(amodel.generator, within=NonNegativeReals,initialize = enforce_inistageon)
amodel.geninioff = Param(amodel.generator, within=NonNegativeReals,initialize = enforce_inistageoff)

#%% generation cost function
amodel.pgenK0 = Param(amodel.generator, within=NonNegativeReals)
amodel.PCost0 = Param(amodel.generator, within=NonNegativeReals)
amodel.PCost1 = Param(amodel.generator, within=NonNegativeReals) 
amodel.PCost2 = Param(amodel.generator, within=NonNegativeReals)
amodel.numcurve = Param(Within=PositiveIntegers,default=3)
amodel.createpoints = {}
amodel.CreatePowerGenerationPiecewisePoints = BuildAction(amodel.generator * amodel.nperiods, rule=gen_piecewise_curve)
amodel.ShutdownCostCoefficient = Param(amodel.generator, within=NonNegativeReals, default=0.0)

#%% vars
amodel.UnitOn = Var(amodel.generator, amodel.nperiods, within=Binary)
amodel.PowerGenerated = Var(amodel.generator, amodel.nperiods, within=NonNegativeReals)
amodel.MaximumPowerAvailable = Var(amodel.generator, amodel.nperiods, within=NonNegativeReals)

amodel.ProductionCost = Var(amodel.generator, amodel.nperiods, within=NonNegativeReals)
amodel.StartupCost = Var(amodel.generator, amodel.nperiods, within=NonNegativeReals)
amodel.ShutdownCost = Var(amodel.generator, amodel.nperiods, within=NonNegativeReals)

amodel.TotalProductionCost = Var(within=NonNegativeReals)
amodel.TotalFixedCost = Var(within=NonNegativeReals)

amodel.ProductionEqualsDemand = Constraint(amodel.nperiods, rule=production_equals_demand_rule)
amodel.EnforceReserveRequirements = Constraint(amodel.nperiods, rule=enforce_reserve_requirements_rule)

amodel.EnforceGeneratorOutputLimitsPartA = Constraint(amodel.generator, amodel.nperiods, rule=enforce_generator_output_limits_rule_part_a)
amodel.EnforceGeneratorOutputLimitsPartB = Constraint(amodel.generator, amodel.nperiods, rule=enforce_generator_output_limits_rule_part_b)
amodel.EnforceGeneratorOutputLimitsPartC = Constraint(amodel.generator, amodel.nperiods, rule=enforce_generator_output_limits_rule_part_c)

amodel.EnforceMaxAvailableRampUpRates = Constraint(amodel.generator, amodel.nperiods, rule=enforce_max_available_ramp_up_rates_rule)
amodel.EnforceMaxAvailableRampDownRates = Constraint(amodel.generator, amodel.nperiods, rule=enforce_max_available_ramp_down_rates_rule)
amodel.ComputeProductionCosts = Piecewise(amodel.generator * amodel.nperiods, amodel.ProductionCost, amodel.PowerGenerated, pw_pts=amodel.createpoints, f_rule=production_cost_function, pw_constr_type='LB')

#%% total cost
amodel.ComputeTotalProductionCost = Constraint(rule=compute_total_production_cost_rule)
amodel.ComputeShutdownCosts = Constraint(amodel.generator, amodel.nperiods, rule=compute_shutdown_costs_rule)
amodel.ComputeTotalFixedCost = Constraint(rule=compute_total_fixed_cost_rule)
amodel.EnforceUpTimeConstraintsInitial = Constraint(amodel.generator, rule=enforce_up_time_constraints_initial)
amodel.EnforceUpTimeConstraintsSubsequent = Constraint(amodel.generator, amodel.nperiods, rule=enforce_up_time_constraints_subsequent)
amodel.EnforceDownTimeConstraintsInitial = Constraint(amodel.generator, rule=enforce_down_time_constraints_initial)
amodel.EnforceDownTimeConstraintsSubsequent = Constraint(amodel.generator, amodel.nperiods, rule=enforce_down_time_constraints_subsequent)
amodel.TotalCostObjective = Objective(rule=total_cost_objective_rule, sense=minimize)

#%% compile
opt = SolverFactory('gurobi')
results = opt.solve(amodel, tee=True, keepfiles=False, options_string="mip_tolerances_integrality=1e-9 mip_tolerances_mipgap=0")
if (results.solver.status != SolverStatus.ok):
    print('Check solver not ok?')
if (results.solver.termination_condition != TerminationCondition.optimal):  
    print('Check solver optimality?') 




