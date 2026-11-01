/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   time.c                                             :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: victoriantriyadi <victoriantriyadi@stud    +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2026/10/23 20:57:49 by victoriantr       #+#    #+#             */
/*   Updated: 2026/10/31 19:51:37 by victoriantr      ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include "codexion.h"

long	now_ms(void)
{
	struct timeval	tv;

	gettimeofday(&tv, NULL);
	return (tv.tv_sec * 1000 + tv.tv_usec / 1000);
}

int	is_stopped(t_sim *sim)
{
	int	stop;

	pthread_mutex_lock(&sim->print_mutex);
	stop = sim->stop;
	pthread_mutex_unlock(&sim->print_mutex);
	return (stop);
}

void	sleep_ms(t_sim *sim, long ms)
{
	long	end;

	end = now_ms() + ms;
	while (now_ms() < end && !is_stopped(sim))
		usleep(500);
}
