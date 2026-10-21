# Referencia del ejecutable — Carbon C-M0

Fecha de análisis: 2026-10-21. Copia local `Need for Speed Carbon/NFSC.exe`, 7.217.152 bytes.

SHA-256: `baaaaec33873d4ba7e4dbae6a5212049ffdcf9679a35d865d7625b4189952fd3`.

PE32 x86; base `0x00400000`, entrada `0x0087e926`, SizeOfImage `0x0082b34e`. Sin recurso de versión, sin sección de protección (no hay SecuROM ni stub de descompresión en la entrada). Se identifica por su hash.

| Sección | RVA | Tamaño virtual | Tamaño en disco | Entropía |
|---|---:|---:|---:|---:|
| .text | 0x1000 | 0x5c0000 | 6.029.312 | 6,52 |
| .rdata | 0x5c1000 | 0x89000 | 561.152 | 5,89 |
| .data | 0x64a000 | 0x184000 | 237.568 | 5,12 |
| .rsrc | 0x7ce000 | 0x5d34e | 385.024 | 3,61 |

348 importaciones de 15 DLL: kernel32 (91), msvcr71 (134), msvcp71 (3), user32 (39), ws2_32 (40), d3dx9_30 (19), advapi32 (11), winmm (3), dinput8, dsound, d3d9, netapi32, rpcrt4, shfolder y ole32.

Diferencias con Carbon que condicionan el port:

- **CRT dinámico.** El juego enlaza `msvcr71.dll`/`msvcp71.dll` en lugar de un CRT estático, incluido el manejo de excepciones C++ (`__CxxFrameHandler`, `_CxxThrowException`). Ambas DLL están en la carpeta del juego y tienen reubicaciones: se traducirán como módulos invitados en direcciones fijas, como `d3dx9_26.dll` en Carbon. msvcr71: base preferida `0x7c340000`, 0x56000 bytes, 837 exportaciones. msvcp71: `0x7c3a0000`, 0x7b000 bytes, 2.903 exportaciones.
- **D3DX 9.30.** `d3dx9_30.dll` no está en la carpeta del juego; se toma de la copia local del runtime de DirectX (`Windows/SysWOW64`), 0x260000 bytes, 332 exportaciones. Efectos desde recursos (`D3DXCreateEffectFromResourceA`) y pool de efectos, como en Carbon.
- La imagen termina en `0x00c2b34e`: los módulos invitados irán a partir de `0x00d00000`.

## NFSCO (modo online de la comunidad)

`NFSCO/bin/nfsc.exe` tiene `.text`, `.rdata` y `.data` idénticos byte a byte a `NFSC.exe` (misma entrada y marca de compilación); solo cambian los recursos. Un único lifting del código del juego sirve para el juego original y como base de NFSCO.

Piezas del mod (código cerrado, compilación de abril de 2026, firmado con certificado DigiCert):

| Archivo | Papel |
|---|---|
| `bootstrapper.exe` | Cargador propio: reserva 9 MB en `0x400000` (sección `.b` vacía), carga `nfsc.exe` en su propio proceso y llama a `palmont.dll!OnAttach`. Monta `NFSCO/files/nfsco` sobre los datos del juego y lee los ajustes en JSON. |
| `palmont.dll` | El mod (1,5 MB, MSVC moderno): cliente de red propio con servidor `nfsco.club` y comprobación de versión del protocolo (los mensajes son los de la biblioteca ENet), overlay ImGui sobre D3D9 con fuentes TTF, chat, comandos (`/race`), Discord IPC, capturas, sustitución de shaders (`NFSCO/shaders/*.cso`) y del registro por `NFSCO/registry.json`. Importa d3d9, ws2_32, iphlpapi, user32, gdi32, imm32, dwmapi, shell32, ole32, winmm y `logging.dll`. |
| `logging.dll` | Registro del mod (`NFSCO/logs`). |
| `server.exe` | Servidor dedicado del mod. |

Los autores de NFSCO han autorizado el port a Android (2026-10-21): se pueden traducir sus binarios, pero no comparten su código fuente. Se les acredita (nfsco.club) en el README y en el launcher.

### Captura de los parches de palmont

`tools/nfsco_capture.c` reproduce el papel del bootstrapper en Windows. Un proceso hijo suspendido reserva la imagen en `0x400000`, palmont en `0x01060000` y el pool de trampolines en `0x01200000`. Después se carga `nfsc.exe`, se carga una copia de `palmont.dll` reubicada a esa base fija (`tools/rebase_fixed.py`, solo en `work/`) y se llama a `OnAttach`. Las asignaciones ejecutables de palmont se sirven página a página desde el pool, mediante su importación de `VirtualAlloc`.

Resultado (`work/nfsco_patches_v2/`, no se sube a Git): 2.700 bytes cambiados en 574 rangos de la imagen del juego y 0x21000 bytes de trampolines en el pool. Dos ejecuciones dan el mismo código. Solo cambian datos que palmont rellena al arrancar: el valor que sustituye a `0x12345678` en `0x006B5686` y punteros de heap a partir de `0x009C1556`. En Android `OnAttach` se ejecutará traducido con las mismas bases, así que esos datos se recalculan allí.

Otros archivos de la carpeta que no forman parte del juego: `dinput8.dll` (cargador ASI) y `scripts/NFSCarbon.WidescreenFix.asi`/`.ini` (WidescreenFix de ThirteenAG, referencia para la adaptación panorámica, como en los otros ports).

## Idioma

El juego lee el valor de cadena `Language` de `HKLM\Software\Electronic Arts\Need for Speed Carbon` y lo compara, sin distinguir mayúsculas, con la tabla de `0x00A65588`:

`English US`, `English UK`, `French`, `German`, `Italian`, `Spanish`, `Spanish (Mexican)`, `Swedish`, `Danish`, `Czech`, `Hungarian`, `Dutch`, `Korean`, `Chinese (Traditional)`, `Chinese (Simplified)`, `Japanese`, `Thai`, `Polish` y `Finnish`.

Cada entrada lleva el idioma de los textos (`LANGUAGES/<Idioma>_{Frontend,Global,InGame}.bin`) y el de las voces. En Android el launcher escribirá ese valor en el registro invitado, igual que Carbon: Español (`Spanish`), Español de México (`Spanish (Mexican)`) e Inglés (`English US`), más los demás idiomas cuyos `.bin` estén en la copia del usuario.
