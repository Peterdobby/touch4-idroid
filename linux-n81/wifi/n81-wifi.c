// SPDX-License-Identifier: GPL-2.0
/*
 * Minimal Wi-Fi control for the N90 (iPhone 4) over nl80211, without libnl,
 * iw or wpa_supplicant, none of which the phone carries.
 *
 * WPA2-PSK runs on the BCM4329 itself: brcmfmac offers the four-way
 * handshake offload (NL80211_EXT_FEATURE_4WAY_HANDSHAKE_STA_PSK) when the
 * firmware has its supplicant, so a connect only needs the PMK. The laptop
 * derives it (PBKDF2-SHA1 of the passphrase and SSID); the passphrase never
 * reaches the phone.
 *
 * Usage: n90-wifi <cmd> [ifname]
 *   features [if]              what the driver offers
 *   scan [if]                  scan and list networks, strongest first
 *   connect SSID [if]          join a WPA2-PSK network; the PMK, 64 hex
 *                              digits, comes on stdin, not the command line
 *   join FILE [if]             scan and join the first network listed in
 *                              FILE as "SSID<TAB>PMK" lines that is in
 *                              range; exit 3 when none is
 *   link [if]                  the network wlan0 is on, if any
 *   power [on|off] [if]        show or set Wi-Fi power saving
 *   disconnect [if]
 */
#include <errno.h>
#include <linux/genetlink.h>
#include <linux/netlink.h>
#include <linux/nl80211.h>
#include <net/if.h>
#include <poll.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>
#include <sys/time.h>

#define BUF 16384
#define DATA(a) ((void *)((char *)(a) + NLA_HDRLEN))
#define LEN(a) ((int)(a)->nla_len - NLA_HDRLEN)

static int family, grp_scan = -1, grp_mlme = -1;
static unsigned int seq = 1;

struct msg {
	struct nlmsghdr n;
	struct genlmsghdr g;
	char buf[2048];
};

static void start(struct msg *m, int type, int cmd, int flags)
{
	memset(m, 0, sizeof(*m));
	m->n.nlmsg_len = NLMSG_LENGTH(GENL_HDRLEN);
	m->n.nlmsg_type = type;
	m->n.nlmsg_flags = NLM_F_REQUEST | NLM_F_ACK | flags;
	m->n.nlmsg_seq = seq++;
	m->g.cmd = cmd;
	m->g.version = 1;
}

static struct nlattr *put(struct msg *m, int type, const void *data, int len)
{
	struct nlattr *a = (struct nlattr *)((char *)m + NLMSG_ALIGN(m->n.nlmsg_len));

	a->nla_type = type;
	a->nla_len = NLA_HDRLEN + len;
	if (len)
		memcpy(DATA(a), data, len);
	m->n.nlmsg_len = NLMSG_ALIGN(m->n.nlmsg_len) + NLA_ALIGN(a->nla_len);
	return a;
}

static void put_u32(struct msg *m, int type, uint32_t v) { put(m, type, &v, 4); }

static struct nlattr *nest(struct msg *m, int type)
{
	return put(m, type | NLA_F_NESTED, NULL, 0);
}

static void nest_end(struct msg *m, struct nlattr *a)
{
	a->nla_len = (char *)m + m->n.nlmsg_len - (char *)a;
}

static void parse(struct nlattr **tb, int max, void *data, int len)
{
	struct nlattr *a = data;

	memset(tb, 0, sizeof(*tb) * (max + 1));
	while (len >= NLA_HDRLEN && a->nla_len >= NLA_HDRLEN && a->nla_len <= len) {
		int t = a->nla_type & NLA_TYPE_MASK;

		if (t <= max)
			tb[t] = a;
		len -= NLA_ALIGN(a->nla_len);
		a = (struct nlattr *)((char *)a + NLA_ALIGN(a->nla_len));
	}
}

static int open_nl(void)
{
	int fd = socket(AF_NETLINK, SOCK_RAW | SOCK_CLOEXEC, NETLINK_GENERIC);
	struct sockaddr_nl sa = { .nl_family = AF_NETLINK };

	if (fd < 0 || bind(fd, (struct sockaddr *)&sa, sizeof(sa))) {
		perror("netlink");
		exit(1);
	}
	return fd;
}

/*
 * Send a request and hand every reply message to cb until the ACK or DONE.
 * Returns 0 or a negative errno from the kernel.
 */
typedef void (*reply_cb)(struct genlmsghdr *g, int len, void *arg);

static int talk(int fd, struct msg *m, reply_cb cb, void *arg)
{
	static char buf[BUF];
	struct sockaddr_nl to = { .nl_family = AF_NETLINK };

	if (sendto(fd, m, m->n.nlmsg_len, 0, (struct sockaddr *)&to, sizeof(to)) < 0)
		return -errno;
	for (;;) {
		int len = recv(fd, buf, sizeof(buf), 0);
		struct nlmsghdr *n = (struct nlmsghdr *)buf;

		if (len < 0)
			return -errno;
		for (; NLMSG_OK(n, len); n = NLMSG_NEXT(n, len)) {
			if (n->nlmsg_seq != m->n.nlmsg_seq)
				continue;
			if (n->nlmsg_type == NLMSG_ERROR)
				return ((struct nlmsgerr *)NLMSG_DATA(n))->error;
			if (n->nlmsg_type == NLMSG_DONE)
				return 0;
			if (cb)
				cb(NLMSG_DATA(n), n->nlmsg_len - NLMSG_HDRLEN, arg);
		}
	}
}

static void family_cb(struct genlmsghdr *g, int len, void *arg)
{
	struct nlattr *tb[CTRL_ATTR_MAX + 1], *grp;
	int rem;

	(void)arg;
	parse(tb, CTRL_ATTR_MAX, (char *)g + GENL_HDRLEN, len - GENL_HDRLEN);
	if (tb[CTRL_ATTR_FAMILY_ID])
		family = *(uint16_t *)DATA(tb[CTRL_ATTR_FAMILY_ID]);
	if (!tb[CTRL_ATTR_MCAST_GROUPS])
		return;
	grp = DATA(tb[CTRL_ATTR_MCAST_GROUPS]);
	rem = LEN(tb[CTRL_ATTR_MCAST_GROUPS]);
	while (rem >= NLA_HDRLEN && grp->nla_len >= NLA_HDRLEN) {
		struct nlattr *g2[CTRL_ATTR_MCAST_GRP_MAX + 1];

		parse(g2, CTRL_ATTR_MCAST_GRP_MAX, DATA(grp), LEN(grp));
		if (g2[CTRL_ATTR_MCAST_GRP_NAME] && g2[CTRL_ATTR_MCAST_GRP_ID]) {
			const char *name = DATA(g2[CTRL_ATTR_MCAST_GRP_NAME]);
			int id = *(uint32_t *)DATA(g2[CTRL_ATTR_MCAST_GRP_ID]);

			if (!strcmp(name, "scan"))
				grp_scan = id;
			else if (!strcmp(name, "mlme"))
				grp_mlme = id;
		}
		rem -= NLA_ALIGN(grp->nla_len);
		grp = (struct nlattr *)((char *)grp + NLA_ALIGN(grp->nla_len));
	}
}

static void resolve(int fd)
{
	struct msg m;

	start(&m, GENL_ID_CTRL, CTRL_CMD_GETFAMILY, 0);
	put(&m, CTRL_ATTR_FAMILY_NAME, "nl80211", 8);
	if (talk(fd, &m, family_cb, NULL) || !family) {
		fprintf(stderr, "no nl80211 (is cfg80211 loaded?)\n");
		exit(1);
	}
}

/* An event socket on one multicast group, opened before the request. */
static int listen_on(int group)
{
	int fd = open_nl();

	if (group < 0 || setsockopt(fd, SOL_NETLINK, NETLINK_ADD_MEMBERSHIP,
				    &group, sizeof(group))) {
		perror("multicast group");
		exit(1);
	}
	return fd;
}

/* Wait for one of two nl80211 events on ifindex; returns the cmd or 0. */
static int wait_event(int fd, int ifindex, int cmd1, int cmd2, int secs,
		      struct nlattr **tb)
{
	static char buf[BUF];
	time_t end = time(NULL) + secs;

	while (time(NULL) < end) {
		struct pollfd p = { .fd = fd, .events = POLLIN };
		struct nlmsghdr *n = (struct nlmsghdr *)buf;
		int len;

		if (poll(&p, 1, 1000) <= 0)
			continue;
		len = recv(fd, buf, sizeof(buf), 0);
		for (; len > 0 && NLMSG_OK(n, len); n = NLMSG_NEXT(n, len)) {
			struct genlmsghdr *g = NLMSG_DATA(n);

			if (n->nlmsg_type != family || (g->cmd != cmd1 && g->cmd != cmd2))
				continue;
			parse(tb, NL80211_ATTR_MAX, (char *)g + GENL_HDRLEN,
			      n->nlmsg_len - NLMSG_HDRLEN - GENL_HDRLEN);
			if (tb[NL80211_ATTR_IFINDEX] &&
			    *(uint32_t *)DATA(tb[NL80211_ATTR_IFINDEX]) != (uint32_t)ifindex)
				continue;
			return g->cmd;
		}
	}
	return 0;
}

static void features_cb(struct genlmsghdr *g, int len, void *arg)
{
	struct nlattr *tb[NL80211_ATTR_MAX + 1];
	int *psk = arg;

	parse(tb, NL80211_ATTR_MAX, (char *)g + GENL_HDRLEN, len - GENL_HDRLEN);
	if (tb[NL80211_ATTR_EXT_FEATURES]) {
		unsigned char *f = DATA(tb[NL80211_ATTR_EXT_FEATURES]);
		int bit = NL80211_EXT_FEATURE_4WAY_HANDSHAKE_STA_PSK;

		if (bit / 8 < LEN(tb[NL80211_ATTR_EXT_FEATURES]))
			*psk = !!(f[bit / 8] & (1 << (bit % 8)));
	}
}

static int features(int fd, int ifindex)
{
	struct msg m;
	int psk = 0, err;

	start(&m, family, NL80211_CMD_GET_WIPHY, NLM_F_DUMP);
	put_u32(&m, NL80211_ATTR_IFINDEX, ifindex);
	put(&m, NL80211_ATTR_SPLIT_WIPHY_DUMP, NULL, 0);
	err = talk(fd, &m, features_cb, &psk);
	if (err) {
		fprintf(stderr, "wiphy: %s\n", strerror(-err));
		return 1;
	}
	printf("psk_offload %s\n", psk ? "yes" : "no");
	return 0;
}

struct bss {
	char ssid[33], bssid[18], sec[12];
	int freq, mbm, status;
	int age_ms;
};

struct bss_list {
	struct bss b[64];
	int n;
};

static void bss_cb(struct genlmsghdr *g, int len, void *arg)
{
	struct nlattr *tb[NL80211_ATTR_MAX + 1], *bb[NL80211_BSS_MAX + 1];
	struct bss_list *l = arg;
	struct bss *b;
	unsigned char *ie, *mac;
	int ielen, wpa = 0, rsn = 0;

	parse(tb, NL80211_ATTR_MAX, (char *)g + GENL_HDRLEN, len - GENL_HDRLEN);
	if (!tb[NL80211_ATTR_BSS] || l->n >= 64)
		return;
	parse(bb, NL80211_BSS_MAX, DATA(tb[NL80211_ATTR_BSS]), LEN(tb[NL80211_ATTR_BSS]));
	if (!bb[NL80211_BSS_BSSID])
		return;
	b = &l->b[l->n++];
	memset(b, 0, sizeof(*b));
	mac = DATA(bb[NL80211_BSS_BSSID]);
	snprintf(b->bssid, sizeof(b->bssid), "%02x:%02x:%02x:%02x:%02x:%02x",
		 mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
	if (bb[NL80211_BSS_FREQUENCY])
		b->freq = *(uint32_t *)DATA(bb[NL80211_BSS_FREQUENCY]);
	if (bb[NL80211_BSS_SIGNAL_MBM])
		b->mbm = *(int32_t *)DATA(bb[NL80211_BSS_SIGNAL_MBM]);
	b->age_ms = bb[NL80211_BSS_SEEN_MS_AGO] ? (int)*(uint32_t *)DATA(bb[NL80211_BSS_SEEN_MS_AGO]) : -1;
	b->status = bb[NL80211_BSS_STATUS] ? (int)*(uint32_t *)DATA(bb[NL80211_BSS_STATUS]) : -1;
	if (!bb[NL80211_BSS_INFORMATION_ELEMENTS])
		return;
	ie = DATA(bb[NL80211_BSS_INFORMATION_ELEMENTS]);
	ielen = LEN(bb[NL80211_BSS_INFORMATION_ELEMENTS]);
	while (ielen >= 2 && ie[1] + 2 <= ielen) {
		if (ie[0] == 0 && ie[1] <= 32) {
			int i;

			memcpy(b->ssid, ie + 2, ie[1]);
			b->ssid[ie[1]] = 0;
			for (i = 0; i < ie[1]; i++)
				if ((unsigned char)b->ssid[i] < 32 || b->ssid[i] == 127)
					b->ssid[i] = '?';
		} else if (ie[0] == 48) {
			rsn = 1;
		} else if (ie[0] == 221 && ie[1] >= 4 && !memcmp(ie + 2, "\x00\x50\xf2\x01", 4)) {
			wpa = 1;
		}
		ielen -= ie[1] + 2;
		ie += ie[1] + 2;
	}
	strcpy(b->sec, rsn ? "wpa2" : wpa ? "wpa" : "open");
}

static int by_signal(const void *a, const void *b)
{
	return ((const struct bss *)b)->mbm - ((const struct bss *)a)->mbm;
}

static int dump_bss(int fd, int ifindex, struct bss_list *l)
{
	struct msg m;

	l->n = 0;
	start(&m, family, NL80211_CMD_GET_SCAN, NLM_F_DUMP);
	put_u32(&m, NL80211_ATTR_IFINDEX, ifindex);
	return talk(fd, &m, bss_cb, l);
}

/* Scan and fill l, strongest first. */
static int do_scan(int fd, int ifindex, struct bss_list *l)
{
	struct nlattr *tb[NL80211_ATTR_MAX + 1], *ssids;
	struct msg m;
	int ev = listen_on(grp_scan), err;

	start(&m, family, NL80211_CMD_TRIGGER_SCAN, 0);
	put_u32(&m, NL80211_ATTR_IFINDEX, ifindex);
	ssids = nest(&m, NL80211_ATTR_SCAN_SSIDS);
	put(&m, 1, NULL, 0);	/* the wildcard SSID: an active scan */
	nest_end(&m, ssids);
	err = talk(fd, &m, NULL, NULL);
	if (err && err != -EBUSY) {
		fprintf(stderr, "scan: %s\n", strerror(-err));
		return 1;
	}
	if (wait_event(ev, ifindex, NL80211_CMD_NEW_SCAN_RESULTS,
		       NL80211_CMD_SCAN_ABORTED, 20, tb) != NL80211_CMD_NEW_SCAN_RESULTS)
		fprintf(stderr, "scan did not finish; showing what is known\n");
	close(ev);
	err = dump_bss(fd, ifindex, l);
	if (err) {
		fprintf(stderr, "scan results: %s\n", strerror(-err));
		return 1;
	}
	qsort(l->b, l->n, sizeof(l->b[0]), by_signal);
	return 0;
}

static int scan(int fd, int ifindex)
{
	static struct bss_list l;
	int i;

	if (do_scan(fd, ifindex, &l))
		return 1;
	for (i = 0; i < l.n; i++)
		printf("%4d dBm %4d MHz %-5s %s %s\n", l.b[i].mbm / 100, l.b[i].freq,
		       l.b[i].sec, l.b[i].bssid, l.b[i].ssid[0] ? l.b[i].ssid : "(hidden)");
	return 0;
}

/* Read cached observations without requesting a scan or joining anything.
 * Tabs/newlines in SSIDs were already sanitized by bss_cb. */
static int sightings(int fd, int ifindex)
{
 static struct bss_list l;
 if (dump_bss(fd, ifindex, &l)) return 1;
 for (int i = 0; i < l.n; i++)
  printf("%s\t%d\t%d\t%d\t%d\t%s\n", l.b[i].bssid, l.b[i].freq,
         l.b[i].mbm / 100, l.b[i].age_ms,
         l.b[i].status == NL80211_BSS_STATUS_ASSOCIATED, l.b[i].ssid);
 return 0;
}

static int link_status(int fd, int ifindex)
{
	static struct bss_list l;
	int i;

	if (dump_bss(fd, ifindex, &l))
		return 1;
	for (i = 0; i < l.n; i++)
		if (l.b[i].status == NL80211_BSS_STATUS_ASSOCIATED) {
			printf("connected %s %s %d MHz %d dBm\n", l.b[i].ssid,
			       l.b[i].bssid, l.b[i].freq, l.b[i].mbm / 100);
			return 0;
		}
	printf("not connected\n");
	return 3;
}

static void power_cb(struct genlmsghdr *g, int len, void *arg)
{
	struct nlattr *tb[NL80211_ATTR_MAX + 1];

	parse(tb, NL80211_ATTR_MAX, (char *)g + GENL_HDRLEN, len - GENL_HDRLEN);
	if (tb[NL80211_ATTR_PS_STATE])
		*(int *)arg = *(uint32_t *)DATA(tb[NL80211_ATTR_PS_STATE]);
}

static int power(int fd, int ifindex, const char *set)
{
	struct msg m;
	int state = -1, err;

	if (set) {
		start(&m, family, NL80211_CMD_SET_POWER_SAVE, 0);
		put_u32(&m, NL80211_ATTR_IFINDEX, ifindex);
		put_u32(&m, NL80211_ATTR_PS_STATE,
			strcmp(set, "on") ? NL80211_PS_DISABLED : NL80211_PS_ENABLED);
		err = talk(fd, &m, NULL, NULL);
		if (err) {
			fprintf(stderr, "power: %s\n", strerror(-err));
			return 1;
		}
	}
	start(&m, family, NL80211_CMD_GET_POWER_SAVE, 0);
	put_u32(&m, NL80211_ATTR_IFINDEX, ifindex);
	err = talk(fd, &m, power_cb, &state);
	if (err) {
		fprintf(stderr, "power: %s\n", strerror(-err));
		return 1;
	}
	printf("power save %s\n", state == NL80211_PS_ENABLED ? "on" :
	       state == NL80211_PS_DISABLED ? "off" : "unknown");
	return 0;
}

static int hexpmk(const char *hex, unsigned char *pmk)
{
	int i;

	if (strlen(hex) != 64)
		return -1;
	for (i = 0; i < 32; i++) {
		unsigned int v;

		if (sscanf(hex + 2 * i, "%2x", &v) != 1)
			return -1;
		pmk[i] = v;
	}
	return 0;
}

static int disconnect(int fd, int ifindex)
{
	struct msg m;
	int err;

	start(&m, family, NL80211_CMD_DISCONNECT, 0);
	put_u32(&m, NL80211_ATTR_IFINDEX, ifindex);
	err = talk(fd, &m, NULL, NULL);
	if (err && err != -ENOTCONN) {
		fprintf(stderr, "disconnect: %s\n", strerror(-err));
		return 1;
	}
	return 0;
}

static int connect_psk(int fd, int ifindex, const char *ssid, const char *hex)
{
	struct nlattr *tb[NL80211_ATTR_MAX + 1];
	unsigned char pmk[32];
	uint32_t ccmp = 0x000fac04, psk = 0x000fac02;
	struct msg m;
	int ev, err, cmd;

	if (strlen(ssid) > 32 || hexpmk(hex, pmk)) {
		fprintf(stderr, "need an SSID of at most 32 bytes and a 64-digit PMK\n");
		return 2;
	}
	ev = listen_on(grp_mlme);
	start(&m, family, NL80211_CMD_CONNECT, 0);
	put_u32(&m, NL80211_ATTR_IFINDEX, ifindex);
	put(&m, NL80211_ATTR_SSID, ssid, strlen(ssid));
	put_u32(&m, NL80211_ATTR_AUTH_TYPE, NL80211_AUTHTYPE_OPEN_SYSTEM);
	put(&m, NL80211_ATTR_PRIVACY, NULL, 0);
	put_u32(&m, NL80211_ATTR_WPA_VERSIONS, NL80211_WPA_VERSION_2);
	put(&m, NL80211_ATTR_CIPHER_SUITES_PAIRWISE, &ccmp, 4);
	put_u32(&m, NL80211_ATTR_CIPHER_SUITE_GROUP, ccmp);
	put(&m, NL80211_ATTR_AKM_SUITES, &psk, 4);
	put(&m, NL80211_ATTR_PMK, pmk, 32);
	err = talk(fd, &m, NULL, NULL);
	memset(pmk, 0, sizeof(pmk));
	memset(&m, 0, sizeof(m));
	if (err) {
		fprintf(stderr, "connect: %s\n", strerror(-err));
		return 1;
	}
	cmd = wait_event(ev, ifindex, NL80211_CMD_CONNECT, NL80211_CMD_DISCONNECT, 30, tb);
	close(ev);
	if (cmd == NL80211_CMD_CONNECT && tb[NL80211_ATTR_STATUS_CODE] &&
	    *(uint16_t *)DATA(tb[NL80211_ATTR_STATUS_CODE]) == 0) {
		printf("connected to %s\n", ssid);
		return 0;
	}
	if (cmd == NL80211_CMD_CONNECT && tb[NL80211_ATTR_STATUS_CODE])
		fprintf(stderr, "refused, status %u\n",
			*(uint16_t *)DATA(tb[NL80211_ATTR_STATUS_CODE]));
	else if (cmd == NL80211_CMD_CONNECT && tb[NL80211_ATTR_TIMED_OUT])
		fprintf(stderr, "timed out\n");
	else if (cmd)
		fprintf(stderr, "disconnected\n");
	else {
		/* Drop the attempt, or brcmf would refuse scans until a reload. */
		fprintf(stderr, "no answer within 30 s\n");
		disconnect(fd, ifindex);
	}
	return 1;
}

/*
 * Join the first network in FILE that is in range. Boris lists them in
 * order of preference, home Wi-Fi before the phone's hotspot.
 */
static int join(int fd, int ifindex, const char *file)
{
	static struct bss_list l;
	char line[160];
	FILE *f;
	int i, tried = 0, joined = 0;

	if (do_scan(fd, ifindex, &l))
		return 1;
	f = fopen(file, "r");
	if (!f) {
		perror(file);
		return 1;
	}
	while (!joined && fgets(line, sizeof(line), f)) {
		char *tab = strchr(line, '\t');

		line[strcspn(line, "\r\n")] = 0;
		if (!tab || tab == line)
			continue;
		*tab = 0;
		for (i = 0; i < l.n && strcmp(line, l.b[i].ssid); i++)
			;
		if (i == l.n)
			continue;
		tried = 1;
		joined = !connect_psk(fd, ifindex, line, tab + 1);
	}
	memset(line, 0, sizeof(line));
	fclose(f);
	if (joined)
		return 0;
	if (!tried)
		printf("no known network in range\n");
	return tried ? 1 : 3;
}

/*
 * Firmware variables, through brcmfmac's vendor command:
 * "get NAME [ARG...]" and "set NAME VALUE...", values being 32-bit words.
 */
static uint32_t var_reply;

static void var_cb(struct genlmsghdr *g, int len, void *arg)
{
	struct nlattr *tb[NL80211_ATTR_MAX + 1], *d[3];

	(void)arg;
	parse(tb, NL80211_ATTR_MAX, (char *)g + GENL_HDRLEN, len - GENL_HDRLEN);
	if (!tb[NL80211_ATTR_VENDOR_DATA])
		return;
	parse(d, 2, DATA(tb[NL80211_ATTR_VENDOR_DATA]), LEN(tb[NL80211_ATTR_VENDOR_DATA]));
	if (d[2] && LEN(d[2]) >= 4)
		memcpy(&var_reply, DATA(d[2]), 4);
}

static int variable(int fd, int ifindex, int writing, int n, char **args)
{
	struct {
		uint32_t cmd;
		int32_t len;
		uint32_t offset, set, magic;
		char data[96];
	} req = { .cmd = writing ? 263 : 262, .offset = 20, .set = writing };
	int raw = !strcmp(args[0], "cmd"), used = raw ? 0 : strlen(args[0]) + 1, i, ret;
	struct msg m;

	if (used > 64 || n > 5 || (raw && n < 3))
		return 2;
	if (raw) {
		req.cmd = strtoul(args[1], 0, 0);
		req.set = 1;
		writing = 1;
		args++;
		n--;
	}
	memcpy(req.data, args[0], used);
	for (i = 1; i < n; i++, used += 4) {
		uint32_t v = strtoul(args[i], 0, 0);

		memcpy(req.data + used, &v, 4);
	}
	req.len = writing ? used : 64;
	start(&m, family, NL80211_CMD_VENDOR, 0);
	put_u32(&m, NL80211_ATTR_IFINDEX, ifindex);
	put_u32(&m, NL80211_ATTR_VENDOR_ID, 0x001018);
	put_u32(&m, NL80211_ATTR_VENDOR_SUBCMD, 1);
	put(&m, NL80211_ATTR_VENDOR_DATA, &req, 20 + used);
	ret = talk(fd, &m, var_cb, NULL);
	if (ret)
		printf("%s: error %d\n", args[0], ret);
	else if (writing)
		printf("%s: ok\n", args[0]);
	else
		printf("%s = %u (0x%x)\n", args[0], var_reply, var_reply);
	return ret != 0;
}

int main(int argc, char **argv)
{
	const char *cmd = argc > 1 ? argv[1] : "";
	int set = !strcmp(cmd, "power") && argc > 2 &&
		  (!strcmp(argv[2], "on") || !strcmp(argv[2], "off"));
	int arg = !strcmp(cmd, "connect") || !strcmp(cmd, "join") || set;
	const char *ifname = !strcmp(cmd, "get") || !strcmp(cmd, "set") ? "wlan0" :
			     argc > (arg ? 3 : 2) ? argv[arg ? 3 : 2] : "wlan0";
	int ifindex = if_nametoindex(ifname), fd;

	if (!ifindex) {
		fprintf(stderr, "no %s\n", ifname);
		return 1;
	}
	if ((!strcmp(cmd, "get") || !strcmp(cmd, "set")) && argc > 2) {
		fd = open_nl();
		resolve(fd);
		return variable(fd, if_nametoindex("wlan0"), cmd[0] == 's', argc - 2, argv + 2);
	}
	fd = open_nl();
	if (!strcmp(cmd, "sightings")) {
		struct timeval timeout = { .tv_sec = 1 };
		setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof timeout);
	}
	resolve(fd);
	if (!strcmp(cmd, "features"))
		return features(fd, ifindex);
	if (!strcmp(cmd, "scan"))
		return scan(fd, ifindex);
	if (!strcmp(cmd, "sightings"))
		return sightings(fd, ifindex);
	if (!strcmp(cmd, "link"))
		return link_status(fd, ifindex);
	if (!strcmp(cmd, "disconnect"))
		return disconnect(fd, ifindex);
	if (!strcmp(cmd, "power"))
		return power(fd, ifindex, set ? argv[2] : NULL);
	if (!strcmp(cmd, "connect") && argc > 2) {
		char hex[80] = "";
		int ret;

		if (fgets(hex, sizeof(hex), stdin))
			hex[strcspn(hex, "\r\n")] = 0;
		ret = connect_psk(fd, ifindex, argv[2], hex);
		memset(hex, 0, sizeof(hex));
		return ret;
	}
	if (!strcmp(cmd, "join") && argc > 2)
		return join(fd, ifindex, argv[2]);
	fprintf(stderr, "usage: n90-wifi features|scan|sightings|link|disconnect [if] | "
		"power [on|off] [if] | connect SSID [if] < pmk | join FILE [if]\n");
	return 2;
}
