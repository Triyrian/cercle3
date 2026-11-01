/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   dongle.c                                           :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: victoriantriyadi <victoriantriyadi@stud    +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2026/10/23 20:57:34 by victoriantr       #+#    #+#             */
/*   Updated: 2026/10/29 12:31:25 by victoriantr      ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include "codexion.h"

int	can_take(t_dongle *d, int id)
{
	return (d->queue.data[0].coder_id == id && !d->taken
		&& now_ms() >= d->available_at);
}

void	wait_dongle(t_dongle *d, int id)
{
	struct timespec	ts;

	if (d->taken || d->queue.data[0].coder_id != id)
	{
		pthread_cond_wait(&d->cond, &d->mutex);
		return ;
	}
	ts.tv_sec = d->available_at / 1000;
	ts.tv_nsec = (d->available_at % 1000) * 1000000;
	pthread_cond_timedwait(&d->cond, &d->mutex, &ts);
}
