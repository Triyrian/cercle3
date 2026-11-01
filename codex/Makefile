NAME		= codexion

CC			= cc
CFLAGS		= -Wall -Wextra -Werror -pthread

INC_DIR		= .
SRC_DIR		= src
OBJ_DIR		= obj

HEADERS		= codexion.h

SRCS		= $(SRC_DIR)/main.c \
			  $(SRC_DIR)/init.c \
			  $(SRC_DIR)/time.c \
			  $(SRC_DIR)/heap.c \
			  $(SRC_DIR)/dongle.c \
			  $(SRC_DIR)/dongles.c \
			  $(SRC_DIR)/coder.c \
			  $(SRC_DIR)/monitor.c

OBJS		= $(SRCS:$(SRC_DIR)/%.c=$(OBJ_DIR)/%.o)

all: $(NAME)

$(NAME): $(OBJS)
	$(CC) $(CFLAGS) $(OBJS) -o $(NAME)

$(OBJ_DIR)/%.o: $(SRC_DIR)/%.c $(HEADERS) | $(OBJ_DIR)
	$(CC) $(CFLAGS) -I $(INC_DIR) -c $< -o $@

$(OBJ_DIR):
	mkdir -p $(OBJ_DIR)

clean:
	rm -rf $(OBJ_DIR)

fclean: clean
	rm -f $(NAME)

re: fclean
	$(MAKE) all

.PHONY: all clean fclean re
