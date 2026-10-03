#pragma once
#include <stdint.h>
int poc_sh_open(const char *name);
int poc_sh_close(int fd);
long poc_sh_write(int fd, const void *data, uint32_t size);
void poc_finish(int success) __attribute__((noreturn));
void poc_console(const char *text);
