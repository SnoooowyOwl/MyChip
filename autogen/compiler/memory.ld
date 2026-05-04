OUTPUT_ARCH(riscv)
ENTRY(_start)

MEMORY
{
  ICACHE (rx)  : ORIGIN = 0x80000000, LENGTH = 8K
  DCACHE (rw)  : ORIGIN = 0x90000000, LENGTH = 8K
}

SECTIONS
{
  .text : ALIGN(4)
  {
    *(.text.start .text.start.*)
    *(.text .text.*)
    *(.srodata .srodata.*)
    *(.rodata .rodata.*)
  } > ICACHE

  .dcache_init : ALIGN(4)
  {
    *(.dcache_init)
  } > DCACHE

  .data : ALIGN(4)
  {
    *(.sdata .sdata.*)
    *(.data .data.*)
  } > DCACHE

  .bss (NOLOAD) : ALIGN(4)
  {
    *(.sbss .sbss.*)
    *(.bss .bss.*)
    *(COMMON)
  } > DCACHE

  /DISCARD/ :
  {
    *(.riscv.attributes)
    *(.comment)
    *(.note*)
    *(.eh_frame*)
  }

  ASSERT(SIZEOF(.text) <= LENGTH(ICACHE), "I-cache image exceeds 8 KiB")
  ASSERT(SIZEOF(.dcache_init) <= LENGTH(DCACHE), "D-cache image exceeds 8 KiB")
  ASSERT(SIZEOF(.data) == 0, "unexpected initialized .data; put constants in .dcache_init")
  ASSERT(SIZEOF(.bss) == 0, "unexpected .bss; use explicit D-cache addresses")
}
