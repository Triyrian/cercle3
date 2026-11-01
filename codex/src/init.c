/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   init.c                                             :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: victoriantriyadi <victoriantriyadi@stud    +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2026/10/23 20:57:38 by victoriantr       #+#    #+#             */
/*   Updated: 2026/10/29 12:31:29 by victoriantr      ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include "codexion.h"

static void	init_dongles(t_sim *sim)
{
	int	i;

	i = 0;
	while (i < sim->n_coders)
	{
		pthread_mutex_init(&sim->dongles[i].mutex, NULL);
		pthread_cond_init(&sim->dongles[i].cond, NULL);
		sim->dongles[i].queue.sched = sim->sched;
		i++;
	}
}

static void	init_coders(t_sim *sim)
{
	int	i;

	sim->start = now_ms();
	i = 0;
	while (i < sim->n_coders)
	{
		sim->coders[i].id = i + 1;
		sim->coders[i].sim = sim;
		sim->coders[i].last_compile = sim->start;
		if (i == sim->n_coders - 1)
		{
			sim->coders[i].first = &sim->dongles[0];
			sim->coders[i].second = &sim->dongles[i];
		}
		else
		{
			sim->coders[i].first = &sim->dongles[i];
			sim->coders[i].second = &sim->dongles[i + 1];
		}
		i++;
	}
}

int	init_sim(t_sim *sim)
{
	sim->coders = malloc(sizeof(t_coder) * sim->n_coders);
	sim->dongles = malloc(sizeof(t_dongle) * sim->n_coders);
	if (!sim->coders || !sim->dongles)
	{
		free(sim->coders);
		free(sim->dongles);
		return (0);
	}
	memset(sim->coders, 0, sizeof(t_coder) * sim->n_coders);
	memset(sim->dongles, 0, sizeof(t_dongle) * sim->n_coders);
	pthread_mutex_init(&sim->print_mutex, NULL);
	init_dongles(sim);
	init_coders(sim);
	return (1);
}

int	run_sim(t_sim *sim)
{
	int	i;
	int	ok;

	if (pthread_create(&sim->monitor, NULL, monitor_routine, sim) != 0)
		return (0);
	i = 0;
	while (i < sim->n_coders && pthread_create(&sim->coders[i].thread,
			NULL, coder_routine, &sim->coders[i]) == 0)
		i++;
	ok = (i == sim->n_coders);
	if (!ok)
	{
		pthread_mutex_lock(&sim->print_mutex);
		sim->stop = 1;
		pthread_mutex_unlock(&sim->print_mutex);
	}
	while (i > 0)
		pthread_join(sim->coders[--i].thread, NULL);
	pthread_join(sim->monitor, NULL);
	return (ok);
}

void	destroy_sim(t_sim *sim)
{
	int	i;

	i = 0;
	while (i < sim->n_coders)
	{
		pthread_mutex_destroy(&sim->dongles[i].mutex);
		pthread_cond_destroy(&sim->dongles[i].cond);
		i++;
	}
	pthread_mutex_destroy(&sim->print_mutex);
	free(sim->coders);
	free(sim->dongles);
}
