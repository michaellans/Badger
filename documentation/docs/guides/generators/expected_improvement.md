# Expected Improvement

Bayesian Optimization (BO) algorithms are machine learning-based algorithms that are particularly well suited to efficiently optimizing noisy objectives with few iterations. Using data collected during and/or prior to optimization, BO algorithms use Bayesian statistics to build a model of the objective function that predicts a distribution of possible function values at each point in parameter space. It then uses an acquisition function to make sampling decisions based on determining the global optimum of the objective function.
<br></br>

**Advantages:**
- Global or local optimization depending on algorithm specifications
- Creates an online surrogate model of the objective and any constraint functions, which can be used during or after optimization
- Can account for observational constraints
- Can incorporate rich prior information about the optimization problem to improve convergence
- Explicitly handles measurement uncertainty and/or noisy objectives
<br></br>

**Disadvantages:**
- Potentially significant computational costs, especially after many iterations
- Numerous hyperparameters which can affect performance
<br></br>

## Parameters
- `turbo_controller` : Trust-region Bayesian Optimization dynamically constrains the search space to a region around the best point. Options are `null`, `OptimizeTurboController`, or `SafetyTurboController`.
- `numerical_optimizer` : Numerical method for finding the maximum value of the aquisition function at each optimization step.
- `max_travel_distances` : Optional list of maximum step sizes, as floats, for each variable. If provided must be the same length as number of variables. Each distance will be applied as an additional constraint on the bounds for each optimization step. For example, if a max_travel_distance of [1.0] is given for a magnet, each step of the optimization will be constrained to a distance of +- 1.0kG from the current value.
<br></br>
<br></br>
