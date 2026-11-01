/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   dongles.c                                          :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: victoriantriyadi <victoriantriyadi@stud    +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2026/10/31 18:00:00 by victoriantr       #+#    #+#             */
/*   Updated: 2026/10/31 18:00:00 by victoriantr      ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include "codexion.h"

static void	request(t_coder *c)
{
	t_request	req;

	req.coder_id = c->id;
	req.deadline = c->last_compile + c->sim->t_burnout;
	pthread_mutex_lock(&c->first->mutex);
	pthread_mutex_lock(&c->second->mutex);
	heap_push(&c->first->queue, req);
	heap_push(&c->second->queue, req);
	pthread_mutex_unlock(&c->second->mutex);
	pthread_mutex_unlock(&c->first->mutex);
}

static t_dongle	*try_take(t_coder *c)
{
	t_dongle	*block;

	pthread_mutex_lock(&c->first->mutex);
	pthread_mutex_lock(&c->second->mutex);
	block = NULL;
	if (!can_take(c->first, c->id))
		block = c->first;
	else if (!can_take(c->second, c->id))
		block = c->second;
	if (!block)
	{
		heap_pop(&c->first->queue);
		heap_pop(&c->second->queue);
		c->first->taken = 1;
		c->second->taken = 1;
	}
	pthread_mutex_unlock(&c->second->mutex);
	pthread_mutex_unlock(&c->first->mutex);
	return (block);
}

int	take_dongles(t_coder *c)
{
	t_dongle	*d;

	request(c);
	d = try_take(c);
	while (d)
	{
		pthread_mutex_lock(&d->mutex);
		if (is_stopped(c->sim))
		{
			pthread_mutex_unlock(&d->mutex);
			return (0);
		}
		if (!can_take(d, c->id))
			wait_dongle(d, c->id);
		pthread_mutex_unlock(&d->mutex);
		d = try_take(c);
	}
	return (1);
}

void	release_dongles(t_coder *c)
{
	long	available_at;

	pthread_mutex_lock(&c->first->mutex);
	pthread_mutex_lock(&c->second->mutex);
	available_at = now_ms() + c->sim->cooldown;
	c->first->taken = 0;
	c->first->available_at = available_at;
	pthread_cond_broadcast(&c->first->cond);
	c->second->taken = 0;
	c->second->available_at = available_at;
	pthread_cond_broadcast(&c->second->cond);
	pthread_mutex_unlock(&c->second->mutex);
	pthread_mutex_unlock(&c->first->mutex);
}

void	wake_all_dongles(t_sim *sim)
{
	int	i;

	i = 0;
	while (i < sim->n_coders)
	{
		pthread_mutex_lock(&sim->dongles[i].mutex);
		pthread_cond_broadcast(&sim->dongles[i].cond);
		pthread_mutex_unlock(&sim->dongles[i].mutex);
		i++;
	}
}
