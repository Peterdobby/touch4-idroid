/* RAM-display compatibility for the explicitly identified TOUCH01/02/03 images.
 * The inherited framebuffer stays lit and has no panel power programming.
 * Preserve the real power backend; accept only an otherwise unsupported ON
 * request when that exact RAM display and the absent power ABI are confirmed.
 * No suspend, panel, battery, or input operations are implemented here. */
#ifdef T4_GB_ABI
#include "t4-gb-api.h"
#else
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#endif

static int t4_read_text(const char *path,char *buffer,unsigned capacity)
{
 int fd;unsigned used=0;ssize_t count;char extra;
 fd=open(path,O_RDONLY);
 if(fd<0)return 0;
 while(used<capacity-1){
  count=read(fd,buffer+used,capacity-1-used);
  if(count<0){if(errno==EINTR)continue;close(fd);return 0;}
  if(!count){buffer[used]=0;close(fd);return 1;}
  used+=(unsigned)count;
 }
 /* Require EOF, including for an exactly full buffer. Never trust a prefix. */
 do{count=read(fd,&extra,1);}while(count<0 && errno==EINTR);
 close(fd);
 if(count)return 0;
 buffer[used]=0;return 1;
}

static int t4_space(char c)
{return c==' ' || c=='\t' || c=='\n' || c=='\r' || c=='\v' || c=='\f';}

static int t4_cmdline_matches(const char *text)
{
 static const char *const tokens[]={"t4_test=T4_ANDROID_TOUCH_01","t4_test=T4_ANDROID_TOUCH_02","t4_test=T4_ANDROID_TOUCH_03"};
 unsigned i,k;
 while(*text){
  while(t4_space(*text))text++;
  if(!*text)break;
  for(k=0;k<sizeof(tokens)/sizeof(tokens[0]);k++){
   const char *token=tokens[k];
   for(i=0;token[i] && text[i]==token[i];i++);
   if(!token[i] && (!text[i] || t4_space(text[i])))return 1;
  }
  while(*text && !t4_space(*text))text++;
 }
 return 0;
}

static int t4_framebuffer_matches(const char *text)
{
 static const char name[]="T4-inherited";unsigned i;
 for(i=0;name[i] && text[i]==name[i];i++);
 return !name[i] && (!text[i] || (text[i]=='\n' && !text[i+1]));
}

static int t4_path_absent(const char *path)
{return access(path,F_OK)<0 && errno==ENOENT;}

static int t4_ram_boot_verified;

/* Zygote loads the preload as root. /proc/cmdline is root-only on this kernel;
 * keep that immutable boot identity across its later setuid/fork. */
#ifndef T4_POWER_HOST_TEST
__attribute__((constructor))
#endif
static void t4_verify_ram_boot(void)
{
 char cmdline[1024],framebuffer[64];
 int saved_errno=errno;
 t4_ram_boot_verified=0;
 if(t4_path_absent("/sys/power") && t4_path_absent("/sys/android_power") &&
    t4_read_text("/proc/cmdline",cmdline,sizeof(cmdline)) && t4_cmdline_matches(cmdline) &&
    t4_read_text("/sys/class/graphics/fb0/name",framebuffer,sizeof(framebuffer)) &&
    t4_framebuffer_matches(framebuffer))t4_ram_boot_verified=1;
 errno=saved_errno;
}

static int t4_ram_display_without_power(void)
{
 char framebuffer[64];
 return t4_ram_boot_verified && t4_path_absent("/sys/power") &&
        t4_path_absent("/sys/android_power") &&
        t4_read_text("/sys/class/graphics/fb0/name",framebuffer,sizeof(framebuffer)) &&
        t4_framebuffer_matches(framebuffer);
}

int set_screen_state(int on)
{
 typedef int (*screen_state_fn)(int);
 void *handle;screen_state_fn original;int result,saved_errno,incoming_errno=errno;
 /* Gingerbread's explicit handle lookup selects the DSO's own symbol. */
 handle=dlopen("/system/lib/libhardware_legacy.so",RTLD_NOW|RTLD_LOCAL);
 if(!handle){errno=ENOSYS;return ENOSYS;}
 original=(screen_state_fn)dlsym(handle,"set_screen_state");
 if(!original || original==set_screen_state){dlclose(handle);errno=ENOSYS;return ENOSYS;}
 errno=incoming_errno;
 result=original(on);saved_errno=errno;
 dlclose(handle);
 if(on==1 && result==ENOENT && t4_ram_display_without_power())result=0;
 errno=saved_errno;
 return result;
}
