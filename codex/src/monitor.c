/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   monitor.c                                          :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: victoriantriyadi <victoriantriyadi@stud    +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2026/10/23 20:57:45 by victoriantr       #+#    #+#             */
/*   Updated: 2026/10/29 12:31:36 by victoriantr      ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include "codexion.h"

static int	check(t_sim *sim)
{
	long	now;
	int		done;
	int		i;

	now = now_ms();
	done = 1;
	i = 0;
	while (i < sim->n_coders)
	{
		if (now - sim->coders[i].last_compile >= sim->t_burnout)
		{
			printf("%ld %d burned out\n", now - sim->start, sim->coders[i].id);
			return (1);
		}
		if (sim->coders[i].compiles < sim->n_compiles)
			done = 0;
		i++;
	}
	return (done);
}

void	*monitor_routine(void *arg)
{
	t_sim	*sim;
	int		stop;

	sim = arg;
	stop = 0;
	while (!stop)
	{
		usleep(500);
		pthread_mutex_lock(&sim->print_mutex);
		if (!sim->stop && check(sim))
			sim->stop = 1;
		stop = sim->stop;
		pthread_mutex_unlock(&sim->print_mutex);
	}
	wake_all_dongles(sim);
	return (NULL);
}
