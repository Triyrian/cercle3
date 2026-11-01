/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   heap.c                                             :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: victoriantriyadi <victoriantriyadi@stud    +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2026/10/23 20:57:36 by victoriantr       #+#    #+#             */
/*   Updated: 2026/10/31 15:16:55 by victoriantr      ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include "codexion.h"

static int	go_first(t_heap *h, t_request *a, t_request *b)
{
	if (h->sched == EDF)
		return (a->deadline < b->deadline);
	return (0);
}

void	heap_push(t_heap *h, t_request req)
{
	if (h->size == 1 && go_first(h, &req, &h->data[0]))
	{
		h->data[1] = h->data[0];
		h->data[0] = req;
	}
	else
		h->data[h->size] = req;
	h->size++;
}

void	heap_pop(t_heap *h)
{
	h->size--;
	h->data[0] = h->data[h->size];
}
