/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   codexion.h                                         :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: victoriantriyadi <victoriantriyadi@stud    +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2026/10/28 15:29:28 by victoriantr       #+#    #+#             */
/*   Updated: 2026/11/01 15:17:27 by victoriantr      ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#ifndef CODEXION_H
# define CODEXION_H

# include <pthread.h>
# include <sys/time.h>
# include <time.h>
# include <unistd.h>
# include <stdlib.h>
# include <stdio.h>
# include <string.h>
# include <limits.h>

typedef enum e_sched
{
	FIFO,
	EDF
}	t_sched;

typedef struct s_request
{
	long	deadline;
	int		coder_id;
}	t_request;

typedef struct s_heap
{
	t_request	data[2];
	int			size;
	t_sched		sched;
}	t_heap;

typedef struct s_dongle
{
	pthread_mutex_t	mutex;
	pthread_cond_t	cond;
	int				taken;
	long			available_at;
	t_heap			queue;
}	t_dongle;

typedef struct s_coder
{
	int				id;
	pthread_t		thread;
	long			last_compile;
	int				compiles;
	t_dongle		*first;
	t_dongle		*second;
	struct s_sim	*sim;
}	t_coder;

typedef struct s_sim
{
	int				n_coders;
	int				t_burnout;
	int				t_compile;
	int				t_debug;
	int				t_refactor;
	int				n_compiles;
	int				cooldown;
	t_sched			sched;

	long			start;
	int				stop;
	pthread_mutex_t	print_mutex;
	pthread_t		monitor;
	t_coder			*coders;
	t_dongle		*dongles;
}	t_sim;

long	now_ms(void);
int		is_stopped(t_sim *sim);
void	sleep_ms(t_sim *sim, long ms);

void	heap_push(t_heap *h, t_request req);
void	heap_pop(t_heap *h);

int		can_take(t_dongle *d, int id);
void	wait_dongle(t_dongle *d, int id);
int		take_dongles(t_coder *c);
void	release_dongles(t_coder *c);
void	wake_all_dongles(t_sim *sim);

void	*coder_routine(void *arg);

void	*monitor_routine(void *arg);

int		init_sim(t_sim *sim);
int		run_sim(t_sim *sim);
void	destroy_sim(t_sim *sim);

#endif
