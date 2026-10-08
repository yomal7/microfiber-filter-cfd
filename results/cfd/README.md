# CFD results

Each row is one OpenFOAM run. Sensor values are what the LCD would show; flows are what leaves through the outlet (filtered) and the overflow (unfiltered). Pictures and summary.json for each run are in the folder of the same name; videos are in the `videos` artifact of the Actions run.

| Inflow (L/min) | Clogging | P1 (kPa) | P2 (kPa) | dP (kPa) | Filtered (L/min) | Overflow (L/min) | Fabric loss (Pa) | Converged* | Folder |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 5 | 0 % | 0.00 | 0.00 | 0.10 | 5.0 | 0.0 | 92 | drift 1 Pa | [q05p0_c00](q05p0_c00/) |
| 5 | 50 % | 0.00 | 0.00 | 0.19 | 5.0 | 0.0 | 185 | drift 3 Pa | [q05p0_c50](q05p0_c50/) |
| 5 | 80 % | 0.00 | 0.00 | 0.48 | 5.0 | 0.0 | 464 | drift 1 Pa | [q05p0_c80](q05p0_c80/) |
| 10 | 0 % | 0.00 | 0.26 | 0.20 | 10.0 | 0.0 | 183 | drift 12 Pa | [q10p0_c00](q10p0_c00/) |
| 10 | 50 % | 0.00 | 0.26 | 0.40 | 10.0 | 0.0 | 369 | drift 7 Pa | [q10p0_c50](q10p0_c50/) |
| 10 | 80 % | 0.00 | 0.26 | 1.02 | 10.0 | 0.0 | 926 | drift 6 Pa | [q10p0_c80](q10p0_c80/) |
| 15 | 0 % | 0.00 | 0.73 | 0.32 | 15.0 | 0.0 | 272 | drift 1 Pa | [q15p0_c00](q15p0_c00/) |
| 15 | 50 % | 0.00 | 0.73 | 0.61 | 15.0 | 0.0 | 551 | drift 23 Pa | [q15p0_c50](q15p0_c50/) |
| 15 | 80 % | 0.62 | 0.63 | 1.47 | 14.1 | 0.9 | 1303 | drift 16 Pa | [q15p0_c80](q15p0_c80/) |
| 20 | 0 % | 0.36 | 1.39 | 0.45 | 20.0 | 0.0 | 360 | drift 39 Pa | [q20p0_c00](q20p0_c00/) |
| 20 | 50 % | 0.73 | 1.37 | 0.84 | 19.8 | 0.2 | 726 | drift 3 Pa | [q20p0_c50](q20p0_c50/) |
| 20 | 80 % | 0.67 | 0.63 | 1.52 | 14.1 | 5.9 | 1303 | drift 33 Pa | [q20p0_c80](q20p0_c80/) |
| 25 | 0 % | 0.79 | 1.76 | 0.51 | 22.3 | 2.7 | 400 | drift 11 Pa | [q25p0_c00](q25p0_c00/) |
| 25 | 50 % | 0.75 | 1.37 | 0.86 | 19.8 | 5.2 | 727 | drift 11 Pa | [q25p0_c50](q25p0_c50/) |
| 25 | 80 % | 0.62 | 0.63 | 1.47 | 14.1 | 10.9 | 1303 | drift 30 Pa | [q25p0_c80](q25p0_c80/) |

*Converged: the solver met its residual targets, or else how much P1/P2 still changed over the last quarter of the iterations.

![CFD check of the quick model](cfd_vs_model.png)
