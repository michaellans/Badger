## Nelder-Mead

Iterative downhill simplex algorithm which seeks to find local optima by sampling initial points and then using a heuristic to choose the next point during each iteration. Nelder-Mead has been widely used inside accelerator physics.
<br></br>

**Advantages:**
- Low computational cost
- Historically proven performance in the context of accelerator physics
- Automatic/adaptive hyperparameter specification depending on problem characteristics
<br></br>

**Disadvantages:**
- Local optimizer – sensitive to initial starting conditions
- Sensitive to measurement noise which can negatively impact convergence to optimum
- Scales poorly to higher dimensional problems
- Cannot handle observational constraints
<br></br>

## Parameters
- `adaptive` : If `True`, dynamically adjust internal parameters based on dimensionality.
<br></br>
<br></br>
