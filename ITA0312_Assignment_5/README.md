# ITA03 Mobile Computing – Assignment 5 (CO5), Part B

This Colab-ready project implements the four Part B experiments described in the assignment PDF:

- B1: Instrumented background-work scheduler (FIFO vs priority), three validation scenarios, decision logs and counters.
- B2: Same-size easy and adversarial workloads using the same constraint thresholds.
- B3: Exact exhaustive UI/feed configuration search versus greedy hill climbing, three small tests, a counterexample, and scaling operation counts.
- B4: Multimedia resolution/bitrate/upload heuristic, sample device profiles, exhaustive comparison, and an engineering decision note.

These are Python simulations, as allowed by the assignment's worked solution. They do not connect to an Android phone or backend. Simulated battery/network/Doze values must be labelled as simulation evidence, not physical device measurements.

## Google Colab

Upload and extract the ZIP, then:

```python
!unzip -q ITA03_Assignment_5_CO5_Colab_Programs.zip
%cd ITA03_Assignment_5_CO5
!pip install -q -r requirements.txt
```

Run each experiment separately:

```python
!python B1_Background_Scheduler/b1_background_scheduler.py
!python B2_Adversarial_Workload/b2_adversarial_workload.py
!python B3_Exact_vs_Approximate_UI/b3_feed_optimization.py
!python B4_Multimedia_Decision/b4_multimedia_decision.py
```

Or run all experiments:

```python
!python run_all.py
```

Each experiment saves CSV data, logs/reports, and graphs in its own folder.

## B1 design

- 12 records, 3 critical records, maximum 3 workers, 20 scheduling ticks.
- FIFO processes arrival order; a blocked item consumes a slot.
- Priority sorts by (priority, arrival); infeasible items are skipped without consuming a slot.
- Feasibility uses permission, battery, network and Doze maintenance-window checks.
- Scenarios: good connectivity, low battery/Doze, and permission revoked at tick 4.

## B2 design

- Two workloads each contain 40 records and use the same priority scheduler and thresholds.
- Easy workload: network good and battery 70%.
- Adversarial workload: first 3 ticks of each 8-tick period are feasible; remaining 5 ticks have poor network, battery 15%, and Doze.

## B3 design

Uses the assignment's cost model:
- Quality levels q and cache sizes c.
- Frame time based on workload and cache hit.
- Cost = frame drops + lambda * energy + quality-loss penalty.
- Exact enumerates every q,c pair.
- Greedy hill-climbing starts at (min(2,L), 2) and checks four orthogonal neighbours.
- Tests use seeds 1, 2, 3; counterexample uses seed 2 and lambda=0.1.
- Scaling tests use N=50, 200, 1000.

## B4 design

Uses the assignment's resolution/bitrate tables and heuristic:
- Battery below 20%: 480p, 1 Mbps, defer upload.
- Otherwise highest resolution whose estimated encode time is <=6 seconds.
- Bitrate is the highest of {1, 2.5, 5} Mbps not exceeding 60% of measured bandwidth.
- Upload now only if bandwidth >=2 Mbps and battery >=20%.
- Compares the heuristic with exhaustive search over 9 resolution/bitrate combinations.

## Evidence and interpretation

The output CSVs and text reports provide reproducible simulation evidence. Wall-clock timings may vary by Colab runtime. Energy is model-estimated, not measured battery consumption.
