/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   main.c                                             :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: victoriantriyadi <victoriantriyadi@stud    +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2026/10/23 20:57:42 by victoriantr       #+#    #+#             */
/*   Updated: 2026/10/28 18:02:07 by victoriantr      ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include "codexion.h"

static int	parse_int(const char *str, int *out)
{
	long	nb;
	int		i;

	if (str[0] == '\0')
		return (0);
	nb = 0;
	i = 0;
	while (str[i] >= '0' && str[i] <= '9')
	{
		nb = nb * 10 + (str[i] - '0');
		if (nb > INT_MAX)
			return (0);
		i++;
	}
	*out = (int)nb;
	return (str[i] == '\0');
}

static int	parse_args(int argc, char **argv, t_sim *sim)
{
	if (argc != 9)
		return (0);
	if (!parse_int(argv[1], &sim->n_coders)
		|| !parse_int(argv[2], &sim->t_burnout)
		|| !parse_int(argv[3], &sim->t_compile)
		|| !parse_int(argv[4], &sim->t_debug)
		|| !parse_int(argv[5], &sim->t_refactor)
		|| !parse_int(argv[6], &sim->n_compiles)
		|| !parse_int(argv[7], &sim->cooldown))
		return (0);
	if (sim->n_coders == 0)
		return (0);
	if (strcmp(argv[8], "fifo") == 0)
		sim->sched = FIFO;
	else if (strcmp(argv[8], "edf") == 0)
		sim->sched = EDF;
	else
		return (0);
	return (1);
}

int	main(int argc, char **argv)
{
	t_sim	sim;
	int		ok;

	memset(&sim, 0, sizeof(sim));
	if (!parse_args(argc, argv, &sim))
	{
		fprintf(stderr, "Error: invalid arguments\n");
		return (1);
	}
	if (sim.n_compiles == 0)
		return (0);
	if (!init_sim(&sim))
	{
		fprintf(stderr, "Error: malloc failed\n");
		return (1);
	}
	ok = run_sim(&sim);
	destroy_sim(&sim);
	if (!ok)
		fprintf(stderr, "Error: pthread_create failed\n");
	return (!ok);
}
