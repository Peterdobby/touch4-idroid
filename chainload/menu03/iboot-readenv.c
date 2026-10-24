/* Read-only query against the already running controlled iBoot environment. */
#include <libirecovery.h>
#include <stdio.h>
#include <stdlib.h>
int main(void) {
    irecv_client_t c=NULL;
    irecv_error_t e=irecv_open_with_ecid(&c,0ULL);
    if(e!=IRECV_E_SUCCESS){fprintf(stderr,"open: %s\n",irecv_strerror(e));return 2;}
    const char *names[]={"t4-menu-status","boot-partition","boot-ramdisk","boot-path",NULL};
    for(int i=0;names[i];i++) {
        char *s=NULL;e=irecv_getenv(c,names[i],&s);
        printf("%s: %s (API %d)\n",names[i],s?s:"<absent>",(int)e);free(s);
    }
    irecv_close(c);return 0;
}
