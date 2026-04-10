# IPv6 Guide for OpenWRT

## Key Concepts

### 1. Why IPv6 differs from IPv4

```
┌─────────────────────────────────────────────────────────────┐
│ IPv4 vs IPv6                                                │
├─────────────────────────────────────────────────────────────┤
│ IPv4: 192.168.1.1                                           │
│       └─ 4 decimal octets = 32 bits                        │
│       └─ ~4.3 billion addresses                             │
│                                                             │
│ IPv6: 2800:484:8f7e:3200::1                                │
│       └─ 8 hex groups = 128 bits                           │
│       └─ 340 undecillion addresses                          │
│       └─ Enough for 5×10²⁸ IPs per person                  │
└─────────────────────────────────────────────────────────────┘
```

### 2. Hexadecimal notation

IPv6 uses base 16 (hexadecimal):
```
Decimal: 0  1  2  3  4  5  6  7  8  9  10  11  12  13  14  15
Hex:     0  1  2  3  4  5  6  7  8  9   a   b   c   d   e   f
```

Examples: `8f7e` hex = `36734` decimal, `ff` hex = `255` decimal

### 3. Abbreviation rules

Full address: `2800:0484:8f7e:3200:0000:0000:0000:0371`

**Rule 1:** Drop leading zeros per group → `2800:484:8f7e:3200:0:0:0:371`

**Rule 2:** Replace one longest run of all-zero groups with `::` → `2800:484:8f7e:3200::371`

(`::` can only appear once in an address)

---

## IPv6 Address Structure

Example WAN address: `2800:484:8f7e:3200:6038:e0ff:fe12:9d41/64`

```
┌────────────────┬──────┬──────────────────────────┬────┐
│  Global Prefix │Subnet│  Interface ID (Host)     │Mask│
├────────────────┼──────┼──────────────────────────┼────┤
│ 2800:484:8f7e  │ 3200 │ 6038:e0ff:fe12:9d41     │ /64│
├────────────────┼──────┼──────────────────────────┼────┤
│   48 bits      │16 bit│        64 bits           │    │
│  (ISP assigns) │ (you)│   (device identifier)    │    │
└────────────────┴──────┴──────────────────────────┴────┘
```

- **Bits 0–47**: assigned by your ISP
- **Bits 48–63**: you choose subnets (3200, 3201, 3202 …)
- **Bits 64–127**: each device auto-generates its own ID

---

## Types of IPv6 Addresses

### Global Unicast (2000::/3) — Public Internet

Range `2000::` to `3fff::`. Routable on the public Internet, equivalent to IPv4 public IPs.

### Link-Local (fe80::/10) — Physical Link Only

Range `fe80::` to `febf::`. Valid only on the directly connected link; not forwarded by routers. Analogous to `169.254.x.x` in IPv4.

### Unique Local Address — ULA (fc00::/7) — Private Network

Range `fc00::` to `fdff::`. Analogous to `192.168.x.x`. Not routable on the Internet; stays stable across ISP changes; useful for internal services.

### Multicast (ff00::/8) — Multiple Recipients

- `ff02::1` — all nodes on the link
- `ff02::2` — all routers on the link
- `ff02::fb` — mDNS

IPv6 has no broadcast; multicast replaces it.

### Special Addresses

| Address | Meaning |
|---------|---------|
| `::1` | Loopback (equivalent to `127.0.0.1`) |
| `::` | Unspecified address |
| `::ffff:192.168.1.1` | IPv4-mapped IPv6 address |

---

## Prefix Lengths

```
/64 → first 64 bits = network, last 64 bits = hosts (18.4 quintillion host addresses)
```

| Prefix | /64 subnets | Typical use |
|--------|-------------|-------------|
| /128   | 0 (1 IP)    | Single host, loopback |
| /64    | 1           | Standard LAN |
| /60    | 16          | Home with multiple VLANs |
| /56    | 256         | Home / small business |
| /48    | 65,536      | Enterprise / campus |
| /32    | 16M         | Regional ISP |

---

## How SLAAC Works (Stateless Address Autoconfiguration)

```
1. Device powers on
   └─ Generates Link-Local: fe80::<derived from MAC>

2. Sends Router Solicitation (RS)
   └─ "Is there a router here?"

3. Router replies with Router Advertisement (RA)
   ┌─────────────────────────────────────┐
   │ Prefix: 2800:484:8f7e:32d0::/64   │
   │ Gateway: fe80::6238:e0ff:fe12:9d41 │
   │ DNS: 2001:4860:4860::8888          │
   └─────────────────────────────────────┘

4. Device builds its address:
   Prefix + Interface ID
   = 2800:484:8f7e:32d0:xxxx:xxxx:xxxx:xxxx

5. Duplicate Address Detection (DAD)
   └─ "Is anyone else using this IP?"
   └─ If no reply → address is used

6. Device fully configured: global IPv6 + gateway + DNS
```

### Interface ID generation

**EUI-64 method (traditional):**
```
MAC: 60:38:e0:12:9d:41
Insert ff:fe in middle: 60:38:e0:ff:fe:12:9d:41
Flip bit 7 of byte 1:   62:38:e0:ff:fe:12:9d:41
→ Interface ID: 6238:e0ff:fe12:9d41
```

**Privacy Extensions (modern):** random ID, rotated periodically — does not expose MAC.

---

## Prefix Delegation

Your ISP does not give you a single IP; it delegates a full range:

```
ISP says: "Here is 2800:484:8f7e:3200::/56"
          = 256 individual /64 networks for you:
   2800:484:8f7e:3200::/64  ← subnet 0
   2800:484:8f7e:3201::/64  ← subnet 1
   ...
   2800:484:8f7e:32ff::/64  ← subnet 255

Your router picks one (e.g. 32d0) for the LAN.
```

---

## Why Two Address Families? (Global + ULA)

| | Global (2800:484:…) | ULA (fd89:…) |
|--|--|--|
| Purpose | Internet access | Internal communication |
| Stability | Changes if you switch ISPs | Never changes |
| Routeable | Yes (public Internet) | No |
| Best for | External services | IoT, printers, internal servers |

---

## Useful Commands

```bash
# Ping Google DNS (IPv6)
ping6 -c 4 2001:4860:4860::8888

# Show IPv6 addresses
ip -6 addr show

# Show IPv6 routes
ip -6 route show

# IPv6 traceroute
traceroute6 google.com
```

---

## References

- [test-ipv6.com](https://test-ipv6.com) — verify your IPv6 connectivity
- [Hurricane Electric IPv6 Certification](https://ipv6.he.net/certification/) — free course
- [RFC 4291](https://www.rfc-editor.org/rfc/rfc4291) — IPv6 addressing architecture specification
