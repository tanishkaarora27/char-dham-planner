# Viva cheat-sheet

1. **What is the state, and why four parts?**
   `(location, dhams visited, day, time of day)`. Location alone is not enough: the same town means
   different things depending on which dhams are done, how late it is (night ban, fatigue) and the date
   (season risk).

2. **What exactly is g(n)?**
   Base driving hours + expected landslide delay (sensitivity x block probability x hours lost) + a
   penalty for driving in the last 4 hours before the 8 PM ban + a fatigue penalty beyond 6 hours a day
   + 1 hour per overnight + 2 hours per buffer day. All in "effective hours"; all weights are assumptions.

3. **What is h(n) and why is it admissible?**
   Fastest link to any unvisited dham + MST over the unvisited dhams and home, on base hours. The real
   remaining trip is a path through those towns, a path is a spanning tree, and the MST is the cheapest
   spanning tree. Penalties only add cost, so h never overestimates.

4. **Is it consistent? Why did you not use the plain MST with the current town inside?**
   Yes: a move changes h by at most the fastest-road time, which is at most the step cost. The plain
   version can break consistency at junction towns (the junction acts like a Steiner point), so the
   current town is attached by its one fastest link. A test checks over 1,000 state-action pairs.

5. **Why A\* and not Dijkstra, BFS, greedy or AO\*?**
   Dijkstra is optimal but unguided (149,734 expansions vs 81,524). BFS minimises actions, not cost
   (122.47 vs 112.87). Greedy follows h only, so it ignores risk. AO\* is for AND-OR problem decomposition;
   a tour is a single path.

6. **How does a buffer day get placed?**
   "Drive + buffer" is its own action. It costs a spare day but cuts the hours lost if that stretch is
   blocked from 24 to 1. A\* picks it only where the expected saving beats the cost, which at default
   settings is the Joshimath-Badrinath stretch (15% assumed block chance).

7. **Why is your A\* plan 14 days when the naive plan is 11?**
   The naive plan packs 8 to 9 hour driving days and keeps no slack. With our weights, shorter days and one
   buffer day cost less overall (112.87 vs 119.18) and cut expected delay from 2.07 to 1.78 days. Change
   the weights in `graph.json` and the balance changes.

8. **Where does the data come from, and what are the limits?**
   Distances and times are approximate; every risk number is an assumption, clearly labelled. Blockages
   are expected costs, not simulated. Real use would need official road-status and weather data.
