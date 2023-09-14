import unittest
from badger.core import (run_routine_xopt, evaluate_points, Routine, instantiate_env)
import copy
from pandas import DataFrame
from badger.utils import merge_params
from badger.factory import get_env
from xopt.generators import get_generator
from badger.tests.mock.plugins.environments.test import Environment
import pandas as pd
import os

class TestCore(unittest.TestCase):    
    def __init__(self, *args, **kwargs) -> None:
        super(TestCore, self).__init__(*args, **kwargs)
        self.count = 0
        self.points_eval = None
        self.candidates = None 

        data = {"x0": [0.5], "x1": [0.5], "x2": [0.5], "x3": [0.5]},
        data_eval_target = {"x0": [0.5], "x1": [0.5], "x2": [0.5], "x3": [0.5], "f": [1]},

        self.points = pd.DataFrame(data)
        
        self.points_eval_target = pd.DataFrame(data_eval_target)

        self.test_evaluate_points_cases = [
            (self.points, 
             self.mock_routine, 
             self.evaluate_points_callback, 
             self.points_eval_target)]

        
    def mock_routine(self):
        test_routine = {
            "name": "routine-for-core-test",
            "algo": "upper_confidence_bound",
            "env": "test",
            "algo_params": {
                "model": None,
                "turbo_controller": None,
                "use_cuda": False,
                "model_constructor": {
                    "name": "standard",
                    "use_low_noise_prior": True,
                    "covar_modules": {},
                    "mean_modules": {},
                    "trainable_mean_keys": [],
                },
                "numerical_optimizer": {
                    "name": "LBFGS",
                    "n_raw_samples": 20,
                    "n_restarts": 20,
                    "max_iter": 2000,
                },
                "max_travel_distances": None,
                "fixed_features": None,
                "n_candidates": 1,
                "n_monte_carlo_samples": 128,
                "beta": 2.0,
                "start_from_current": True,
            },
            "env_params": {},
            "config": {
                "variables": [
                    {"x0": [-1, 1]},
                    {"x1": [-1, 1]},
                    {"x2": [-1, 1]},
                    {"x3": [-1, 1]},
                ],
                "objectives": [{"f": "MAXIMIZE"}],
                "constraints": None,
                "states": None,
                "domain_scaling": None,
                "tags": None,
                "init_points": {"x0": [0.5], "x1": [0.5], "x2": [0.5], "x3": [0.5]},
            },
        }
        
        # Initialize routine
        Environment, configs_env = get_env(test_routine['env'])
        _configs_env = merge_params(configs_env, {'params': test_routine['env_params']})
        environment = instantiate_env(Environment, _configs_env)

        # self.env_ready(environment)
        
        variables = {key: value for dictionary in test_routine['config']['variables']
                        for key, value in dictionary.items()}
        objectives = {key: value for dictionary in test_routine['config']['objectives']
                        for key, value in dictionary.items()}
        vocs = {
                'variables': variables,
                'objectives': objectives,
            }
        
        generator_class = get_generator(test_routine['algo'])
        
        try:
            del test_routine['algo_params']['start_from_current']
        except KeyError:
            pass
        
        del test_routine['algo_params']['n_candidates']
        del test_routine['algo_params']['fixed_features']

        test_routine_copy = copy.deepcopy(test_routine['algo_params'])

        generator = generator_class(vocs=vocs, **test_routine_copy)

        # TODO -- this need changing to remove try except
        try:
            initial_points = test_routine['config']['init_points']
            initial_points = DataFrame.from_dict(initial_points)
            if initial_points.empty:
                    raise KeyError
        except KeyError:  # start from current
            initial_points = environment.get_variables(generator.vocs.variable_names)
            initial_points = DataFrame(initial_points, index=[0])

        test_routine_xopt = Routine(environment=environment, generator=generator,
                                initial_points=initial_points)
        
        return test_routine_xopt


    def mock_active_callback(self):
        self.count += 1

        if self.count >= 5:
            return 2
        else:
            return 0

    def mock_generate_callback(self, candidates):
        self.candidates_list.append(candidates)

    def mock_evaluate_callback(self, points_eval):
        self.points_eval_list.append(points_eval) 

    def mock_pf_callback(self, pf):
        self.pf = pf 

    def mock_states_callback(self, states):
        self.states = states 
 
    def mock_dump_file_callback(self):
        return "test.yaml"   

    def test_run_routine_xopt(self):
        routine = self.mock_routine()
        run_routine_xopt(routine, self.mock_active_callback, self.mock_generate_callback,
                         self.mock_evaluate_callback, self.mock_pf_callback, self.mock_states_callback, 
                         self.mock_dump_file_callback)
        
        assert len(self.candidates_list) == self.count  
        assert len(self.points_eval_list) == self.count

        assert self.pf is not None 
        assert self.states is None 
        
        path = "./test.yaml"
        assert os.path.exists(path) == True

    def evaluate_points_callback(self, points_eval):
         self.points_eval = points_eval 

    def test_evaluate_points(self):
        routine = self.mock_routine()
        
        assert evaluate_points(self.points, routine, self.evaluate_points_callback) == self.points_eval_target 
        assert self.points_eval == self.points_eval_target


