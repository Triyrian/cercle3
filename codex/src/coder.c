/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   coder.c                                            :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: victoriantriyadi <victoriantriyadi@stud    +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2026/10/23 20:57:31 by victoriantr       #+#    #+#             */
/*   Updated: 2026/10/29 12:31:21 by victoriantr      ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include "codexion.h"

static void	log_state(t_coder *c, char *msg)
{
	pthread_mutex_lock(&c->sim->print_mutex);
	if (!c->sim->stop)
		printf("%ld %d %s\n", now_ms() - c->sim->start, c->id, msg);
	pthread_mutex_unlock(&c->sim->print_mutex);
}

static int	start_compile(t_coder *c)
{
	long	time;

	pthread_mutex_lock(&c->sim->print_mutex);
	time = now_ms();
	if (c->sim->stop || time - c->last_compile >= c->sim->t_burnout)
	{
		pthread_mutex_unlock(&c->sim->print_mutex);
		return (0);
	}
	c->last_compile = time;
	time -= c->sim->start;
	printf("%ld %d has taken a dongle\n", time, c->id);
	printf("%ld %d has taken a dongle\n", time, c->id);
	printf("%ld %d is compiling\n", time, c->id);
	pthread_mutex_unlock(&c->sim->print_mutex);
	return (1);
}

static int	compile(t_coder *c)
{
	if (!start_compile(c))
	{
		release_dongles(c);
		return (0);
	}
	sleep_ms(c->sim, c->sim->t_compile);
	pthread_mutex_lock(&c->sim->print_mutex);
	c->compiles++;
	pthread_mutex_unlock(&c->sim->print_mutex);
	log_state(c, "is debugging");
	release_dongles(c);
	return (1);
}

void	*coder_routine(void *arg)
{
	t_coder	*c;

	c = arg;
	if (c->first == c->second)
	{
		log_state(c, "has taken a dongle");
		return (NULL);
	}
	if (c->id % 2 == 0)
		usleep(1000);
	while (take_dongles(c) && compile(c))
	{
		sleep_ms(c->sim, c->sim->t_debug);
		log_state(c, "is refactoring");
		sleep_ms(c->sim, c->sim->t_refactor);
	}
	return (NULL);
}
