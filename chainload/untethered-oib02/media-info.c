/* Read registry metadata only. No user-client open, flash, NVRAM or MMIO. */
typedef unsigned int U; typedef const void *CF;
extern int printf(const char *,...);
extern CF IOServiceMatching(const char *);
extern U IOServiceGetMatchingService(U,CF);
extern int IORegistryEntryGetParentEntry(U,const char *,U *);
extern int IORegistryEntryGetName(U,char *);
extern int IORegistryEntryCreateCFProperties(U,CF *,CF,U);
extern int IOObjectRelease(U);
extern void CFShow(CF); extern void CFRelease(CF);
int main(void){
 U s=IOServiceGetMatchingService(0,IOServiceMatching("AppleNANDFirmware"));
 if(!s)return 2;
 for(int i=0;i<4 && s;i++){
  char name[128]={0};CF props=0;IORegistryEntryGetName(s,name);
  printf("FIRMWARE_ANCESTOR_%d %s\n",i,name);
  if(!IORegistryEntryCreateCFProperties(s,&props,0,0) && props){CFShow(props);CFRelease(props);}
  U parent=0;int e=IORegistryEntryGetParentEntry(s,"IOService",&parent);
  IOObjectRelease(s);s=e?0:parent;
 }
 if(s)IOObjectRelease(s);
 return 0;
}
