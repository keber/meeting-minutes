# {{TITULO}}

**Fecha:** {{FECHA}}
**Duración aprox. de la reunión:** {{DURACION}}
**Participantes:** {{PARTICIPANTES}}

<!--
La minuta tiene dos partes y NO son dos resoluciones del mismo contenido.
La Parte 1 son conclusiones; la Parte 2 es la evidencia que las sostiene.
Si la Parte 1 resume a la Parte 2, nadie lee la segunda y se duplica todo.

Parte 1 — ACTA         qué se decidió, cuánto cuesta, qué bloquea, quién sigue.
                       Lector: quien estuvo en la reunión. Se lee en 2 minutos.
Parte 2 — DESARROLLO   por qué se decidió eso y con qué detalle.
                       Lector: quien no estuvo, quien audita, quien escribe
                       casos de prueba. Se consulta, no se lee.
-->

---

# Parte 1 — Acta

## Resumen ejecutivo

{{RESUMEN_EJECUTIVO}}

<!-- Un párrafo. Qué se acordó y con qué foco. No enumerar los temas: para eso
     está la tabla de abajo. -->

---

## Temas y trazabilidad

{{TABLA_TEMAS}}

<!--
| # | Tema | Work item | Esfuerzo | Conf. | Timestamp |
|---|---|---|---|---|---|

Una fila por tema, en el orden en que se trataron. El esfuerzo es la cifra
dicha en voz alta; la cita literal que la respalda va en la Parte 2.
Sin work item confirmado: dejar la celda en `TODO`, nunca inventar un ID.
Cerrar con el total declarado en la reunión, si lo hubo, y con los work items
del sprint que nadie mencionó.
-->

---

## Decisiones y acuerdos

{{DECISIONES}}

<!-- Lista plana, un renglón por decisión, con la parte decidida en negrita.
     Sin checkboxes. Solo lo acordado, no lo discutido. -->

---

## Riesgos, bloqueos y dependencias

{{RIESGOS}}

<!--
Bullets con etiqueta tipada en negrita:
- **Riesgo:** …
- **Bloqueo:** …
- **Dependencia:** …

Un renglón cada uno. Si algo quedó sin tratar y debería haberse tratado,
decirlo como TODO en vez de completarlo con criterio propio.
-->

---

## Próximos pasos

{{PROXIMOS_PASOS}}

<!-- Lista ordenada, verbo en infinitivo al inicio. Un renglón por paso. -->

---

# Parte 2 — Desarrollo

## Detalle por tema

{{TEMAS}}

<!--
### N) Título del tema ({{TIPO}} {{ID}})
- Qué se planteó y qué se resolvió.
- Inventario de campos, pantallas o rutas mencionados.
- Resoluciones técnicas: si alguien preguntó algo y se respondió, queda la
  respuesta, no la pregunta.
- Estimación: la cita literal con su timestamp.
- **Del work item ({{ID}}):** detalle tomado de la descripción en Azure DevOps,
  marcado como tal para distinguirlo de lo hablado en la reunión.

Acá SÍ cabe el detalle: es la parte que se consulta meses después y la materia
prima de la que se alimenta el knowledge base del proyecto. Lo que no cabe es
color conversacional sin valor de decisión.
-->

---

## Glosario breve

{{GLOSARIO}}

<!-- Solo términos que aparecen en esta minuta y están definidos en el overlay
     de dominio. Un término nuevo se lista como `- **Término:** TODO`. -->

---

**Fuentes:** {{FUENTES}}
**Confianza general:** {{CONFIANZA}}
**TODO:** {{TODO}}

<!--
Contrato heredado de rag-v1/index.md: toda minuta declara sus fuentes, su nivel
de confianza (Alta / Media / Baja) y lo que quedó sin resolver.
No inventar contenido: lo no derivable se marca TODO.
-->
