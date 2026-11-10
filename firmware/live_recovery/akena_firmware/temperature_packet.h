#pragma once
#include <cstddef>
#include <cstdint>
#include <cmath>

// MLX90614 SMBus PEC: address+W, command, address+R, low byte, high byte.
// Melexis datasheet read-word example B4 07 B5 D2 3A has PEC 30.
inline uint8_t mlxPacketCrc(const uint8_t *bytes, size_t count) {
  uint8_t crc=0;
  for (size_t i=0;i<count;++i) {
    crc^=bytes[i];
    for (unsigned bit=0;bit<8;++bit) crc=(crc&0x80) ? uint8_t((crc<<1)^0x07) : uint8_t(crc<<1);
  }
  return crc;
}
inline bool decodeMlxTemperature(uint8_t address, uint8_t reg, const uint8_t data[3], float &value) {
  const uint8_t packet[]={uint8_t(address<<1),reg,uint8_t((address<<1)|1),data[0],data[1]};
  uint16_t raw=uint16_t(data[0]) | (uint16_t(data[1])<<8);
  value=NAN;
  if (mlxPacketCrc(packet,5)!=data[2] || !raw || (raw&0x8000)) return false;
  value=raw*0.02f-273.15f; return true;
}
