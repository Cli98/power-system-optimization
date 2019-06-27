#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Apr  8 23:39:24 2019

@author: changlinli
"""

from pyomo.environ import ConcreteModel,AbstractModel,Param,RangeSet,Set,BuildAction,Var,Objective,Piecewise,minimize,value
from pyomo.environ import NonNegativeReals,Integers,Binary,PositiveIntegers
from pyomo.opt import SolverStatus,TerminationCondition
from pyomo.opt import SolverFactory

v={}
v[1,1] = 9
v[2,2] = 16
v[3,3] = 25
model = ConcreteModel() 
model.A = RangeSet(1,3)
model.B = RangeSet(1,3)
model.P = Param(model.A, model.B)
model.S = Param(model.A, model.B, initialize=v, default=0)
def s_validate(model, v, i):
   return v > 3.14159
model.S = Param(model.A, validate=s_validate)


def s_init(model, i, j):
    if i == j:
        return i*i
    else:
        return 0.0
model.S1 = Param(model.A, model.B, initialize=s_init)

model = ConcreteModel() 
model.A = Set(initialize=[1,2,3])
def s_validate(model):
    for ele in model:
        if ele < 3.14159:
            return False
    return True
model.s = Param(model.A, validate=False)

model = AbstractModel()
model.A = Set(initialize=[1,2,3])
def s_validate(model):
    for ele in model:
        if ele < 3.14159:
            return False
    return True
model.s = Param(model.A, validate=s_validate)
instance = model.create_instance()