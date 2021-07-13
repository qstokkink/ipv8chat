from base64 import b64encode
from binascii import crc32, unhexlify
from functools import lru_cache
from zlib import compressobj
from struct import pack


def bto_col(ib, cl, ch):  
    r = cl[0] if ib < cl[0] else ib if ib < ch[0] else ch[0]
    g = cl[1] if ib < cl[1] else ib if ib < ch[1] else ch[1]
    b = cl[2] if ib < cl[2] else ib if ib < ch[2] else ch[2]

    return pack('>B', r) + pack('>B', g) + pack('>B', b)
    

def pack_chunk(chunk_type, chunk_data):
    chunk_content = chunk_type + chunk_data
    return pack('>I', len(chunk_data)) + chunk_content + pack('>I', crc32(chunk_content))


@lru_cache
def ipv8_ec25519_toimg(public_key_bin):
    usable_bytes = public_key_bin[10:74]  # First 10 bytes are "LibNaCLPK"

    img_w = 8
    img_h = 8

    color_map = {d: bto_col(d, usable_bytes[:3], usable_bytes[-3:]) for d in usable_bytes}
    s_colors = sorted(color_map.keys())
    palette_index = {d: i for i, d in enumerate(s_colors)}

    png_header = b'\x89\x50\x4e\x47\x0d\x0a\x1a\x0a'
    ihdr_chunk = (pack('>I', img_w) +  # Width
                  pack('>I', img_h) +  # Height
                  pack('>B', 8) +  # Depth
                  pack('>B', 3) +  # Color type
                  pack('>B', 0) + 
                  pack('>B', 0) +
                  pack('>B', 0))
    plte_chunk = b''.join(color_map[d] for d in s_colors)
    idat_chunk = b''.join(pack('>B', palette_index[d]) for d in usable_bytes)

    # Add scanline format to each scanline (0 for each line)
    tchunk = b''
    for x in range(img_w):
        tchunk += b'\x00' + idat_chunk[x*img_w:x*img_w+img_w]
    idat_chunk = tchunk

    iend_chunk = b''

    idat_chunk_compressor = compressobj(wbits=8)
    idat_chunk = idat_chunk_compressor.compress(idat_chunk)
    idat_chunk += idat_chunk_compressor.flush()

    png = (png_header +
           pack_chunk(b'IHDR', ihdr_chunk) +
           pack_chunk(b'PLTE', plte_chunk) +
           pack_chunk(b'IDAT', idat_chunk) +
           pack_chunk(b'IEND', iend_chunk))

    return b64encode(png)


__all__ = ["ipv8_ec25519_toimg"]
