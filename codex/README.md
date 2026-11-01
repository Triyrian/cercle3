*This project has been created as part of the 42 curriculum by vtriyadi.*

# Codexion

## Description

Codexion is a concurrency simulation in C with POSIX threads. `n` coders sit
around a round table with `n` USB dongles, one between each pair of
neighbours. A coder needs both neighbouring dongles to compile, then debugs,
then refactors, and starts again. A dongle needs a cooldown after it is
released. A coder who waits too long without compiling burns out. The
simulation ends when every coder has compiled enough times, or when one of
them burns out.

When two coders want the same dongle, the scheduler decides who gets it
first:
- **fifo**: the first to ask;
- **edf**: the coder closest to burnout.

## Instructions

```sh
make
./codexion number_of_coders time_to_burnout time_to_compile time_to_debug \
           time_to_refactor number_of_compiles_required dongle_cooldown scheduler
./codexion 5 3000 200 200 200 10 400 fifo
```

Times are in milliseconds, numbers are non-negative integers, and the
scheduler is `fifo` or `edf`. Invalid input prints an error and exits with
status 1. Each output line is `timestamp coder_id message`.

To check for data races, run the program under `valgrind --tool=helgrind`,
under `valgrind --tool=drd`, or build it with `-fsanitize=thread`.

## Blocking cases handled

- **Deadlock.** A coder takes both dongles at once or none, so they never
  hold one while waiting for the other. This breaks Coffman's *hold and
  wait* condition. Mutexes are always locked in the same order, so there is
  no circular wait.
- **Starvation.** Each dongle has a small priority queue (fifo or edf).
  A request is added to both dongles' queues at the same time, so the two
  queues always agree on who goes first.
- **Cooldown.** A released dongle stays unavailable until its cooldown ends.
  A coder waiting for it sleeps on a condition variable instead of looping.
- **Burnout detection.** A monitor thread checks every coder continuously.
  It prints the burnout and stops the simulation in the same critical
  section, so no message comes after it.
- **Log serialization.** All output goes through one mutex, so lines never
  mix.
- **Single coder.** There is only one dongle, so the coder can never compile
  and burns out.

## Thread synchronization mechanisms

- **One `pthread_mutex_t` per dongle** protects the dongle's state and its
  queue.
- **One `pthread_cond_t` per dongle** lets waiting coders sleep until that
  dongle is released.
- **One print mutex** protects the output, the stop flag, and each coder's
  last compile time and compile count. Coders and the monitor share this
  data, so neither side reads it while the other is writing.
- **Monitor and coders.** Coders record their progress under the print
  mutex, and the monitor reads it under the same mutex. To end the
  simulation, the monitor sets the stop flag and wakes every waiting coder.
  Each coder then sees the flag and exits.

## Resources

- `man pthread_mutex_lock`, `pthread_cond_wait`, `pthread_cond_timedwait`
- E. G. Coffman et al., *System Deadlocks* (1971)
- E. W. Dijkstra, the dining philosophers problem
- [Earliest deadline first scheduling](https://en.wikipedia.org/wiki/Earliest_deadline_first_scheduling)
- [Valgrind manual: Helgrind and DRD](https://valgrind.org/docs/manual/manual.html)

**Use of AI.** AI were used as pair programmers:
- design of the synchronization;
- simplifying the code;
- reviewing for races;
- testing.

ChatGPT was used to explain concepts. I understand and can modify every part
of the program.
