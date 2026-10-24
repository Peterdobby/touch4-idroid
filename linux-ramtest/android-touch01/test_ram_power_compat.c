/* Host-only mocks: no loader, power, framebuffer, or device access. */
#include <assert.h>
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

static void *mock_dlopen(const char *,int);
static void *mock_dlsym(void *,const char *);
static int mock_dlclose(void *);
static int mock_access(const char *,int);
static int mock_open(const char *,int,...);
static ssize_t mock_read(int,void *,size_t);
static int mock_close(int);
#define dlopen mock_dlopen
#define dlsym mock_dlsym
#define dlclose mock_dlclose
#define access mock_access
#define open mock_open
#define read mock_read
#define close mock_close
#define T4_POWER_HOST_TEST
#include "ram-power-compat.c"
#undef dlopen
#undef dlsym
#undef dlclose
#undef access
#undef open
#undef read
#undef close

static const char *cmdline,*framebuffer;
static int modern_error,legacy_error,original_result,expected_on;
static int open_failure,read_failure,interrupt_read,loader_failure,symbol_failure;
static unsigned original_calls,loader_closes,guard_calls,offsets[2];
static const int original_errno=ETIMEDOUT;

static int mock_original(int on)
{assert(on==expected_on);original_calls++;errno=original_errno;return original_result;}
static void *mock_dlopen(const char *path,int flags)
{
 assert(!strcmp(path,"/system/lib/libhardware_legacy.so"));
 assert(flags==(RTLD_NOW|RTLD_LOCAL));
 return loader_failure ? 0 : (void *)offsets;
}
static void *mock_dlsym(void *handle,const char *symbol)
{
 assert(handle==(void *)offsets && !strcmp(symbol,"set_screen_state"));
 if(symbol_failure==1)return 0;
 return symbol_failure==2 ? (void *)set_screen_state : (void *)mock_original;
}
static int mock_dlclose(void *handle)
{assert(handle==(void *)offsets);loader_closes++;errno=EIO;return 0;}
static int mock_access(const char *path,int mode)
{
 int error;
 guard_calls++;assert(mode==F_OK);
 if(!strcmp(path,"/sys/power"))error=modern_error;
 else {assert(!strcmp(path,"/sys/android_power"));error=legacy_error;}
 errno=error;return error ? -1 : 0;
}
static int mock_open(const char *path,int flags,...)
{
 int fd;
 assert(flags==O_RDONLY);
 if(!strcmp(path,"/proc/cmdline"))fd=10;
 else {assert(!strcmp(path,"/sys/class/graphics/fb0/name"));fd=11;}
 if(open_failure==fd){errno=EACCES;return -1;}
 offsets[fd-10]=0;return fd;
}
static ssize_t mock_read(int fd,void *buffer,size_t capacity)
{
 const char *text;size_t remaining;
 assert(fd==10 || fd==11);
 if(interrupt_read){interrupt_read=0;errno=EINTR;return -1;}
 if(read_failure==fd){errno=EIO;return -1;}
 text=fd==10 ? cmdline : framebuffer;
 remaining=strlen(text)-offsets[fd-10];
 if(capacity>7)capacity=7; /* Exercise partial reads. */
 if(capacity>remaining)capacity=remaining;
 memcpy(buffer,text+offsets[fd-10],capacity);offsets[fd-10]+=(unsigned)capacity;
 return (ssize_t)capacity;
}
static int mock_close(int fd)
{assert(fd==10 || fd==11);return 0;}
static void reset(void)
{
 cmdline="console=t4fb0 t4_test=T4_ANDROID_TOUCH_01 t4fb=0x08104580\n";
 framebuffer="T4-inherited\n";
 modern_error=legacy_error=ENOENT;original_result=ENOENT;expected_on=1;
 open_failure=read_failure=interrupt_read=loader_failure=symbol_failure=0;
 original_calls=loader_closes=guard_calls=0;
}
static void check(int expected)
{
 t4_verify_ram_boot();guard_calls=0;
 assert(set_screen_state(expected_on)==expected);
 assert(original_calls==1 && loader_closes==1 && errno==original_errno);
}
int main(void)
{
 unsigned i;char oversized[1100];
 reset();check(0);
 reset();interrupt_read=1;check(0);
 reset();framebuffer="T4-inherited";check(0);
 reset();cmdline="t4_test=T4_ANDROID_TOUCH_01";check(0);
 reset();cmdline="console=t4fb0\tt4_test=T4_ANDROID_TOUCH_02\n";check(0);
 reset();expected_on=0;check(ENOENT);assert(!guard_calls);
 reset();expected_on=2;check(ENOENT);assert(!guard_calls);
 reset();original_result=0;check(0);assert(!guard_calls);
 reset();original_result=EACCES;check(EACCES);assert(!guard_calls);
 reset();original_result=EIO;check(EIO);assert(!guard_calls);
 reset();modern_error=0;check(ENOENT);
 reset();legacy_error=0;check(ENOENT);
 reset();modern_error=EACCES;check(ENOENT);
 reset();legacy_error=EACCES;check(ENOENT);
 reset();cmdline="t4_test=T4_ANDROID_ADB_01";check(ENOENT);
 reset();cmdline="t4_test=T4_ANDROID_TOUCH_03";check(0);
 reset();cmdline="t4_test=T4_ANDROID_TOUCH_04";check(ENOENT);
 reset();cmdline="xt4_test=T4_ANDROID_TOUCH_01";check(ENOENT);
 reset();cmdline="t4_test=T4_ANDROID_TOUCH_01_extra";check(ENOENT);
 reset();cmdline="t4_test=T4_ANDROID_TOUCH_02_extra";check(ENOENT);
 reset();framebuffer="Other framebuffer\n";check(ENOENT);
 reset();framebuffer="T4-inherited_extra\n";check(ENOENT);
 for(i=10;i<=11;i++){
  reset();open_failure=(int)i;check(ENOENT);
  reset();read_failure=(int)i;check(ENOENT);
 }
 memset(oversized,'x',sizeof(oversized)-1);oversized[sizeof(oversized)-1]=0;
 memcpy(oversized,"t4_test=T4_ANDROID_TOUCH_01 ",28);
 reset();cmdline=oversized;check(ENOENT); /* Reject a truncated, valid-looking prefix. */
 reset();t4_verify_ram_boot();open_failure=10;
 assert(set_screen_state(1)==0); /* system_server cannot read root-only cmdline. */
 reset();open_failure=10;t4_verify_ram_boot();open_failure=0;
 assert(set_screen_state(1)==ENOENT); /* Never promote a denied boot later. */
 reset();t4_verify_ram_boot();modern_error=0;
 assert(set_screen_state(1)==ENOENT);
 reset();t4_verify_ram_boot();framebuffer="Other framebuffer";
 assert(set_screen_state(1)==ENOENT);
 reset();loader_failure=1;
 assert(set_screen_state(1)==ENOSYS && !original_calls && !loader_closes);
 for(i=1;i<=2;i++){
  reset();symbol_failure=(int)i;
  assert(set_screen_state(1)==ENOSYS && !original_calls && loader_closes==1);
 }
 puts("RAM_POWER_COMPAT_PASS: exact RAM-display gate, native results preserved, no device access");
 return 0;
}
