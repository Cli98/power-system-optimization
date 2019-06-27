#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Apr  2 17:21:12 2019

@author: changlinli
"""
from pyomo.environ import value,Constraint

def check_max_power(m, v, g):
    return v >= value(m.minout[g])

def check_g_min_power(m,v,g):
    return v >= m.minout[g]

def check_inistage(m,v,g):
    return v != 0

def check_inistageon(m,g):
    return value(m.K0State[g]) >= 1

def enforce_inistageon(m,g):
    if not value(m.K0On[g]):
      return 0
    else:
      return min(value(m.nperiods),max(0, \
                     value(m.minUpTime[g]) - value(m.K0State[g])))
      
def enforce_inistageoff(m,g):
    if not value(m.K0On[g]):
      return 0
    else:
      return min(value(m.nperiods),max(0, \
                     value(m.minDownTime[g]) - value(m.K0State[g])))

def gen_piecewise_curve(m,g,t):
    min_power = value(m.minout[g])
    max_power = value(m.maxout[g])
    n = value(m.numcurve)
    width = (max_power - min_power) / float(n)
    m.createpoints[g, t] = [min_power + i*width for i in range(0,n+1)]
    
#def production_cost_function(model, g, t, x):
#    return model.ProductionCost[g,t] == (value(model.PCost0[g]) + value(model.PCost1[g])*model.PowerGenerated[g,t] + value(model.PCost2[g])*model.PowerGenerated[g,t]**2)
#    

def production_cost_function(model, g, t, x):
    return value(model.PCost0[g])+value(model.PCost1[g])*x + value(model.PCost2[g])*x*x

def production_equals_demand_rule(m, t):
    return sum(m.PowerGenerated[g, t] for g in m.generator) == m.demand[t]

def enforce_reserve_requirements_rule(m, t):
    return sum(m.MaximumPowerAvailable[g, t] for g in m.generator) >= m.demand[t] + m.reserve[t]

def enforce_generator_output_limits_rule_part_a(m, g, t):
    return m.minout[g] * m.UnitOn[g, t] <= m.PowerGenerated[g,t]

def enforce_generator_output_limits_rule_part_b(m, g, t):
    return m.PowerGenerated[g,t] <= m.MaximumPowerAvailable[g, t]

def enforce_generator_output_limits_rule_part_c(m, g, t):
    return m.MaximumPowerAvailable[g,t] <= m.maxout[g] * m.UnitOn[g, t]

def enforce_max_available_ramp_up_rates_rule(m, g, t):
   # 4 cases, split by (t-1, t) unit status (RHS is defined as the delta from m.PowerGenerated[g, t-1])
   # (0, 0) - unit staying off:   RHS = maximum generator output (degenerate upper bound due to unit being off) 
   # (0, 1) - unit switching on:  RHS = startup ramp limit 
   # (1, 0) - unit switching off: RHS = standard ramp limit minus startup ramp limit plus maximum power generated (degenerate upper bound due to unit off)
   # (1, 1) - unit staying on:    RHS = standard ramp limit
   if t == 1:
      return m.MaximumPowerAvailable[g, t] <= m.pgenK0[g] + \
                                              m.RampUpLimit[g] * m.K0On[g] + \
                                              m.SURampUpLimit[g] * (m.UnitOn[g, t] - m.K0On[g]) + \
                                              m.maxout[g] * (1 - m.UnitOn[g, t])
   else:
      return m.MaximumPowerAvailable[g, t] <= m.PowerGenerated[g, t-1] + \
                                              m.RampUpLimit[g] * m.UnitOn[g, t-1] + \
                                              m.SURampUpLimit[g] * (m.UnitOn[g, t] - m.UnitOn[g, t-1]) + \
                                              m.maxout[g] * (1 - m.UnitOn[g, t])

# the following constraint encodes Constraint 19 defined in Carrion and Arroyo.

def enforce_max_available_ramp_down_rates_rule(m, g, t):
   # 4 cases, split by (t, t+1) unit status
   # (0, 0) - unit staying off:   RHS = 0 (degenerate upper bound)
   # (0, 1) - unit switching on:  RHS = maximum generator output minus shutdown ramp limit (degenerate upper bound) - this is the strangest case.
   # (1, 0) - unit switching off: RHS = shutdown ramp limit
   # (1, 1) - unit staying on:    RHS = maximum generator output (degenerate upper bound)
   if t == value(m.nperiods):
      return Constraint.Skip
   else:
      return m.MaximumPowerAvailable[g, t] <= \
             m.maxout[g] * m.UnitOn[g, t+1] + \
             m.SDRampDownLimit[g] * (m.UnitOn[g, t] - m.UnitOn[g, t+1])

def compute_total_production_cost_rule(m):
   return m.TotalProductionCost == sum(m.ProductionCost[g, t] for g in m.generator for t in m.periods)

def compute_shutdown_costs_rule(m, g, t):
   if t is 1:
      return m.ShutdownCost[g, t] >= m.ShutdownCostCoefficient[g] * (m.K0On[g] - m.UnitOn[g, t])
   else:
      return m.ShutdownCost[g, t] >= m.ShutdownCostCoefficient[g] * (m.UnitOn[g, t-1] - m.UnitOn[g, t])

def compute_startup_costs_rule(m, g, t):
    K = 0
    if 1<=value(t) and value(t)<=value(m.t_cold[g]+m.minDownTime[g]):
        K = m.hc[g]
    else:
        K = m.cc[g]
    if t is 1:
        return m.StartupCost[g, t] >= K * (-m.K0On[g] + m.UnitOn[g, t])
    else:
        tol = m.K0On[g]
        for i in range(1,t):
            tol+=m.UnitOn[g, t]
        return m.StartupCost[g, t] >= K* (m.UnitOn[g, t]-tol)
  
def compute_total_fixed_cost_rule(m):
   return m.TotalFixedCost == sum(m.StartupCost[g, t] + m.ShutdownCost[g, t] for g in m.generator for t in m.periods)

def enforce_up_time_constraints_initial(m, g):
   if value(m.geninion[g]) is 0:
      return Constraint.Skip
   return sum((1 - m.UnitOn[g, t]) for g in m.generator for t in m.periods if t <= value(m.geninion[g])) == 0.0

def enforce_up_time_constraints_subsequent(m, g, t):
   if t <= value(m.geninion[g]):
      # handled by the EnforceUpTimeConstraintInitial constraint.
      return Constraint.Skip                
   elif t <= (value(m.nperiods) - value(m.minUpTime[g]) + 1):
      # the right-hand side terms below are only positive if the unit was off in the previous time period but on in this one =>
      # the value is the minimum number of subsequent consecutive time periods that the unit is required to be on.
      if t is 1:
         return sum(m.UnitOn[g, n] for n in m.periods if n >= t and n <= (t + value(m.minUpTime[g]) - 1)) >= \
                (m.minUpTime[g] * (m.UnitOn[g, t] - m.K0On[g]))
      else:
         return sum(m.UnitOn[g, n] for n in m.periods if n >= t and n <= (t + value(m.minUpTime[g]) - 1)) >= \
                (m.minUpTime[g] * (m.UnitOn[g, t] - m.UnitOn[g, t-1]))
   else:
      # handle the final (MinimumUpTime[g] - 1) time periods - if a unit is started up in 
      # this interval, it must remain on-line until the end of the time span.
      if t == 1: # can happen when small time horizons are specified
         return sum((m.UnitOn[g, n] - (m.UnitOn[g, t] - m.K0On[g])) for n in m.periods if n >= t) >= 0.0
      else:
         return sum((m.UnitOn[g, n] - (m.UnitOn[g, t] - m.UnitOn[g, t-1])) for n in m.periods if n >= t) >= 0.0

def enforce_down_time_constraints_initial(m, g):
   if value(m.geninioff[g]) is 0: 
      return Constraint.Skip
   return sum(m.UnitOn[g, t] for g in m.generator for t in m.periods if t <= value(m.geninioff[g])) == 0.0

def enforce_down_time_constraints_subsequent(m, g, t):
   if t <= value(m.geninioff[g]):
      # handled by the EnforceDownTimeConstraintInitial constraint.
      return Constraint.Skip
   elif t <= (value(m.nperiods) - value(m.minDownTime[g]) + 1):
      # the right-hand side terms below are only positive if the unit was off in the previous time period but on in this one =>
      # the value is the minimum number of subsequent consecutive time periods that the unit is required to be on.
      if t is 1:
         return sum((1 - m.UnitOn[g, n]) for n in m.periods if n >= t and n <= (t + value(m.minDownTime[g]) - 1)) >= \
                (m.minDownTime[g] * (m.K0On[g] - m.UnitOn[g, t]))
      else:
         return sum((1 - m.UnitOn[g, n] for n in m.periods if n >= t and n <= (t + value(m.minDownTime[g]) - 1))) >= \
                (m.minDownTime[g] * (m.UnitOn[g, t-1] - m.UnitOn[g, t]))
   else:
      # handle the final (MinimumDownTime[g] - 1) time periods - if a unit is shut down in
      # this interval, it must remain off-line until the end of the time span.
      if t == 1: # can happen when small time horizons are specified
         return sum(((1 - m.UnitOn[g, n]) - (m.K0On[g] - m.UnitOn[g, t])) for n in m.periods if n >= t) >= 0.0
      else:
         return sum(((1 - m.UnitOn[g, n]) - (m.UnitOn[g, t-1] - m.UnitOn[g, t])) for n in m.periods if n >= t) >= 0.0

def total_cost_objective_rule(m):
   return m.TotalProductionCost + m.TotalFixedCost

def modifyind(dataframe):
    dic = dataframe.to_dict()
    return {k+1: v for k, v in dic.items()}

def bounds_rule(m,g,t):
    return (m.minout[g],m.maxout[g])