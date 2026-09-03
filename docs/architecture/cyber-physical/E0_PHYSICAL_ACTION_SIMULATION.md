# E0 Physical Action Simulation — detached local candidate

E0 is simulation only. `PhysicalActionSpec` binds canonical SI units, coordinate
frame, calibration revision/digest, exact object scope, temporal scope and
bounded displacement/speed/force/energy. The provider class is
`DIGITAL_TWIN_ONLY` and carries no hardware, authority-minting or external
effect capability.

The deterministic simulator compares the spec to an independently supplied
digital-twin snapshot and fails closed on unit, frame, calibration, object,
pose, heartbeat, sensing, protected-zone, safety-controller, authority or
limit substitution. A PASS receipt says only `SIMULATED_VERIFIED` and
`physical_effect=NONE`; it explicitly records `NOT_PROVEN_BY_SIMULATION` for
hardware safety.

No actuator provider, robotics runtime, network, process launch or filesystem
mutation is introduced by E0. Hardware execution remains outside this step.
