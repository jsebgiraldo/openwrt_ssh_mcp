# 📘 GUÍA COMPLETA DE IPv6 PARA PRINCIPIANTES

## 🎯 CONCEPTOS CLAVE QUE DEBES ENTENDER

### 1. ¿Por qué IPv6 es diferente de IPv4?

```
┌─────────────────────────────────────────────────────────────┐
│ IPv4 vs IPv6                                                │
├─────────────────────────────────────────────────────────────┤
│ IPv4: 192.168.1.1                                          │
│       └─ 4 números (0-255) = 32 bits                       │
│       └─ ~4.3 mil millones de direcciones                  │
│                                                             │
│ IPv6: 2800:484:8f7e:3200::1                                │
│       └─ 8 grupos hexadecimales = 128 bits                 │
│       └─ 340 undecillones de direcciones                   │
│       └─ Suficiente para 5×10²⁸ IPs por persona           │
└─────────────────────────────────────────────────────────────┘
```

### 2. Notación Hexadecimal

IPv6 usa base 16 (hexadecimal):
```
Decimal: 0  1  2  3  4  5  6  7  8  9  10  11  12  13  14  15
Hex:     0  1  2  3  4  5  6  7  8  9   a   b   c   d   e   f
```

**Ejemplos:**
- `8f7e` en hex = `36734` en decimal
- `ff` en hex = `255` en decimal
- `2800` en hex = `10240` en decimal

### 3. Reglas de Abreviación

**Dirección completa:**
```
2800:0484:8f7e:3200:0000:0000:0000:0371
```

**Regla 1: Omitir ceros a la izquierda**
```
2800:484:8f7e:3200:0000:0000:0000:0371
     ↑ Se elimina el 0 inicial
```

**Regla 2: Reemplazar grupos de ceros con `::`**
```
2800:484:8f7e:3200:0000:0000:0000:0371
                    └─────┬──────┘
2800:484:8f7e:3200::0371
                    ↑ Solo se puede usar :: UNA vez
```

**Versión final:**
```
2800:484:8f7e:3200::371
```

---

## 📊 ESTRUCTURA DE UNA DIRECCIÓN IPv6

### Anatomía Detallada

Tu dirección WAN: `2800:484:8f7e:3200:6038:e0ff:fe12:9d41/64`

```
┌────────────────┬──────┬──────────────────────────┬────┐
│    Prefijo     │Subnet│  Interface ID (Host)     │Mask│
│    Global      │  ID  │                          │    │
├────────────────┼──────┼──────────────────────────┼────┤
│ 2800:484:8f7e  │ 3200 │ 6038:e0ff:fe12:9d41     │ /64│
├────────────────┼──────┼──────────────────────────┼────┤
│   48 bits      │16 bit│        64 bits           │    │
│  (Tu ISP)      │(Tú)  │    (Dispositivo)         │    │
└────────────────┴──────┴──────────────────────────┴────┘
        ↓           ↓              ↓
    Routing     Subredes    Identificador único
    global      locales     del dispositivo
```

**Explicación:**
- **Bits 0-47**: Tu ISP te asigna (2800:484:8f7e)
- **Bits 48-63**: Tú decides subredes (3200, 3201, 3202...)
- **Bits 64-127**: Cada dispositivo genera su ID único

---

## 🌍 TIPOS DE DIRECCIONES IPv6

### 1. Global Unicast (2000::/3) - Internet Público

```
Tu router tiene:
2800:484:8f7e:3200::371         ← IP única de WAN

Rango: 2000:: hasta 3fff::
└─ Enrutables en Internet público
└─ Como IPs públicas en IPv4
```

### 2. Link-Local (fe80::/10) - Red Local Física

```
Tu router tiene:
fe80::6238:e0ff:fe12:9d41

┌─────────────────────────────────────────┐
│ Solo válida en el cable/WiFi conectado │
│ No cruza routers                        │
│ Usada para comunicación entre vecinos  │
│ Como 169.254.x.x en IPv4                │
└─────────────────────────────────────────┘

Rango: fe80:: hasta febf::
```

### 3. Unique Local Address - ULA (fc00::/7) - Red Privada

```
Tu router tiene:
fd89:e85:a6f0::1

┌──────────────────────────────────────────┐
│ Red privada (como 192.168.x.x)          │
│ No ruteable en Internet                  │
│ Permanece igual aunque cambies de ISP   │
│ Útil para servicios internos            │
└──────────────────────────────────────────┘

Rango: fc00:: hasta fdff::
```

### 4. Multicast (ff00::/8) - Múltiples Destinatarios

```
Ejemplos:
ff02::1  ← Todos los nodos en el enlace local
ff02::2  ← Todos los routers en el enlace local
ff02::fb ← mDNS (Bonjour/Avahi)

└─ No hay broadcast en IPv6, se usa multicast
```

### 5. Direcciones Especiales

```
::1         ← Loopback (como 127.0.0.1 en IPv4)
::          ← Dirección no especificada (0.0.0.0)
::ffff:192.168.1.1  ← IPv4 mapeada a IPv6
```

---

## 🔢 ENTENDIENDO LAS MÁSCARAS (/XX)

### Visualización del Prefijo

```
/64 significa: Primeros 64 bits son RED, últimos 64 son HOSTS

2800:484:8f7e:3200 : 6038:e0ff:fe12:9d41
└─────64 bits──────┘ └──────64 bits──────┘
      RED                   HOSTS
   (fijo para            (18,446,744,073,709,551,616
    esta LAN)             direcciones posibles)
```

### Tamaños Comunes

| Prefijo | Subredes /64 | Uso Típico |
|---------|--------------|------------|
| /128    | 0 (1 IP)     | Host único, loopback |
| /64     | 1            | LAN estándar (recomendado) |
| /60     | 16           | Hogar con múltiples VLANs |
| /56     | 256          | Hogar grande / pequeña empresa |
| /48     | 65,536       | Empresa / campus |
| /32     | 16M          | ISP regional |

**Tu caso:**
```
ISP te dio:   /56 = 256 subredes /64 disponibles
Usas en LAN:  /60 = 16 subredes /64
              └─ Desperdicias 240 subredes, pero está bien
```

---

## 🚀 CÓMO FUNCIONA SLAAC (Auto-Configuración)

### Proceso Paso a Paso

```
1. Dispositivo enciende
   └─ Genera Link-Local: fe80::<basado en MAC>

2. Envía Router Solicitation (RS)
   └─ "¿Hay algún router aquí?"

3. Router responde con Router Advertisement (RA)
   ┌─────────────────────────────────────────┐
   │ "Soy el router, usa este prefijo:"     │
   │ Prefijo: 2800:484:8f7e:32d0::/64       │
   │ Gateway: fe80::6238:e0ff:fe12:9d41     │
   │ DNS: 2001:4860:4860::8888              │
   └─────────────────────────────────────────┘

4. Dispositivo construye su dirección
   Prefijo del router + ID de interfaz
   2800:484:8f7e:32d0:: + <ID generado>
   = 2800:484:8f7e:32d0:xxxx:xxxx:xxxx:xxxx

5. Prueba DAD (Duplicate Address Detection)
   └─ "¿Alguien más usa esta IP?"
   └─ Si no hay respuesta, la usa

6. Dispositivo configurado automáticamente
   ✅ IPv6 global
   ✅ Gateway predeterminado
   ✅ DNS (si se anuncia)
```

### Generación de Interface ID

**Método EUI-64 (tradicional):**
```
MAC address: 60:38:e0:12:9d:41

1. Insertar ff:fe en medio
   60:38:e0:ff:fe:12:9d:41

2. Invertir bit universal/local (7º bit del 1er byte)
   60 en binario: 01100000
   Invertir 7º:   01100010 = 62

3. Resultado:
   6238:e0ff:fe12:9d41
   └─ Tu interface ID en WAN
```

**Método moderno (Privacy Extensions):**
- Genera ID aleatorio
- Cambia periódicamente
- Más privado (no expone tu MAC)

---

## 🛠️ TU CONFIGURACIÓN ESPECÍFICA

### Flujo de Datos en tu Red

```
INTERNET (IPv6 puro)
    │
    │ Tu ISP delega: 2800:484:8f7e:3200::/56
    │                (256 redes /64)
    ▼
┌───────────────────────────────────────────┐
│ WAN INTERFACE (wan6)                      │
│ • DHCPv6 Client                           │
│ • 2800:484:8f7e:3200::371/128  (DHCPv6)  │
│ • 2800:484:8f7e:3200:xxxx/64   (SLAAC)   │
│ • Gateway: fe80::963c:96ff:fe45:63ac     │
└───────────────────────────────────────────┘
    │
    │ Usa subred: 2800:484:8f7e:32d0::/60
    │             (una de las 256 disponibles)
    ▼
┌───────────────────────────────────────────┐
│ LAN INTERFACE (br-lan)                    │
│ • 2800:484:8f7e:32d0::1/60 (Estática)    │
│ • fd89:e85:a6f0::1/60      (ULA)         │
│ • Anuncia: 2800:484:8f7e:32d0::/64       │
│ • RA Server + DHCPv6 Server              │
└───────────────────────────────────────────┘
    │
    │ Anuncia prefijo a dispositivos
    ▼
┌─────────┬─────────┬─────────┬─────────┐
│   PC    │  Phone  │ Tablet  │   IoT   │
│         │         │         │         │
│ Global: │ Global: │ Global: │ Global: │
│ ::xxxx  │ ::yyyy  │ ::zzzz  │ ::wwww  │
│         │         │         │         │
│ ULA:    │ ULA:    │ ULA:    │ ULA:    │
│ fd89::2 │ fd89::3 │ fd89::4 │ fd89::5 │
└─────────┴─────────┴─────────┴─────────┘
```

### ¿Por qué tienes 2 redes? (Global + ULA)

**Global (2800:484:8f7e:32d0::/60):**
- Para acceso a Internet
- Puede cambiar si cambias de ISP
- Pública y ruteable

**ULA (fd89:e85:a6f0::/60):**
- Para comunicación interna
- Nunca cambia
- Funciona aunque Internet falle
- Útil para IoT, impresoras, servidores locales

---

## 🔍 PREGUNTAS FRECUENTES

### ¿Por qué veo 3 direcciones en mi PC?

```
Tu PC típicamente tiene:
1. Link-Local (fe80::xxxx)     ← Comunicación local
2. Global (2800:484:...)        ← Internet público
3. ULA (fd89:...)               ← Red privada interna

Esto es NORMAL y esperado en IPv6
```

### ¿Cómo sabe mi PC cuál dirección usar?

```
1. Para Internet: Usa Global (2800:...)
2. Para LAN:      Prefiere ULA (fd89:...), pero usa Global si es necesario
3. Para vecinos:  Usa Link-Local (fe80::)

El sistema operativo elige automáticamente (RFC 6724)
```

### ¿Necesito NAT con IPv6?

```
❌ NO en la mayoría de casos

IPv4: NAT es necesario (pocas IPs públicas)
      192.168.1.x → NAT → IP pública única

IPv6: Cada dispositivo tiene IP pública propia
      Sin NAT (end-to-end connectivity)
      Firewall protege, no NAT
```

### ¿Qué es Prefix Delegation?

```
Tu ISP no te da UNA IP, te da un RANGO completo:

┌──────────────────────────────────────────┐
│ ISP dice: "Aquí tienes                   │
│            2800:484:8f7e:3200::/56"      │
│                                          │
│ Eso significa 256 redes /64 para ti:    │
│   2800:484:8f7e:3200::/64  ← Subred 0   │
│   2800:484:8f7e:3201::/64  ← Subred 1   │
│   2800:484:8f7e:3202::/64  ← Subred 2   │
│   ...                                    │
│   2800:484:8f7e:32ff::/64  ← Subred 255 │
└──────────────────────────────────────────┘

Tu router escoge una (32d0) para LAN
```

---

## 📝 COMANDOS ÚTILES

### Verificar Conectividad

```bash
# Ping a Google DNS IPv6
ping6 -c 4 2001:4860:4860::8888

# Ver tus direcciones IPv6
ip -6 addr show

# Ver rutas IPv6
ip -6 route show

# Traceroute IPv6
traceroute6 google.com
```

### Pruebas desde PC

```bash
# Windows
ping 2001:4860:4860::8888
ipconfig | findstr "IPv6"

# Linux/Mac
ping6 2001:4860:4860::8888
ifconfig | grep inet6
```

---

## 🎓 RECURSOS PARA APRENDER MÁS

1. **Test IPv6**: https://test-ipv6.com
   - Ve si tu conexión IPv6 funciona

2. **IPv6 Visual Subnet Calculator**: https://www.ultratools.com/tools/ipv6CIDRToRange
   - Calcula rangos de red

3. **Hurricane Electric IPv6 Certification**: https://ipv6.he.net/certification/
   - Curso gratuito con certificado

4. **RFC 4291**: Especificación de direccionamiento IPv6
   - https://www.rfc-editor.org/rfc/rfc4291

---

## ✅ RESUMEN DE TU CONFIGURACIÓN

```
Estado:     ✅ FUNCIONAL
ISP Prefix: 2800:484:8f7e:3200::/56 (256 redes /64)
LAN Prefix: 2800:484:8f7e:32d0::/60 (16 redes /64)
ULA:        fd89:e85:a6f0::/60
Conectividad: ✅ Internet IPv6 funciona (ping exitoso)
RA/SLAAC:   ✅ Dispositivos obtienen IPs automáticamente
DHCPv6:     ✅ Activo

Recomendaciones:
• Cambiar /60 → /64 en LAN (más simple)
• Configurar DNS IPv6 explícitamente
• Verificar reglas de firewall
```

¡Ahora entiendes IPv6! 🎉
