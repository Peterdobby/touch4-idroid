/* Minimal ARM32 Bionic 2.3 ABI used by the standalone RAM power wrapper.
 * dlfcn constants: AOSP android-2.3.7_r1/libc/include/dlfcn.h (saved in
 * research/idroid-legacy/analysis/bionic-2.3.7/libc_include_dlfcn.h).
 * Function imports are checked against the shipped libc.so/libdl.so.
 * No host/newlib structures or errno accessor are used on the device. */
#ifndef T4_GB_API_H
#define T4_GB_API_H
typedef unsigned size_t;
typedef int ssize_t;
extern void *dlopen(const char *,int);
extern void *dlsym(void *,const char *);
extern int dlclose(void *);
extern int open(const char *,int,...);
extern ssize_t read(int,void *,size_t);
extern ssize_t write(int,const void *,size_t);
extern int close(int);
extern int access(const char *,int);
extern int *__errno(void);
#define errno (*__errno())
#define RTLD_NOW 0
#define RTLD_LOCAL 0
#define O_RDONLY 0
#define F_OK 0
#define ENOENT 2
#define EINTR 4
#define ENOSYS 38
#endif
