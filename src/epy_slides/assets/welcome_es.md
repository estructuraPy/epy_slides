---
title: epy_slides — Manual de usuario
subtitle: Construya presentaciones en Markdown
author: ANM Ingeniería
date: 2026-06-18
theme: corporate
aspect-ratio: "16:9"
transition: slide
slide-number: true
footer: epy_slides — Manual de usuario
---

## Bienvenido a epy_slides
<!-- layout: section -->

## Qué construye aquí
<!-- layout: title-content -->

- Escriba la presentación una sola vez, en **Markdown**
- Vea una vista previa **reveal.js** en vivo mientras escribe
- Exporte la misma fuente a **PDF**, **HTML** y **PowerPoint**

::: {.callout-note title="Una fuente, tres formatos"}
Todo este manual es, en sí mismo, una presentación de epy_slides. Ábralo
cuando quiera desde *Ayuda ▸ Manual de usuario*.
:::

## El editor de un vistazo
<!-- layout: image-caption -->

![El editor Markdown (izquierda) y la vista previa en vivo (derecha)](__SHOT_EDITOR__){width=78%}

## La barra de herramientas, de izquierda a derecha
<!-- layout: cards -->

:::: {.cards}
::: {.card}
#### Diapositivas
Inserte una diapositiva desde un layout, o un salto de diapositiva en blanco.
:::
::: {.card}
#### Contenido
Viñetas, columnas, citas, imágenes, tablas, ecuaciones, código, llamados,
diagramas y notas del orador.
:::
::: {.card}
#### Exportar
PDF, HTML y PowerPoint — más el cambio de tema e idioma en vivo desde *Ver*.
:::
::::

## Escribir diapositivas
<!-- layout: title-content -->

- Una línea que empieza con `## ` inicia una **nueva diapositiva**
- Un solo `# ` inicia un **divisor de sección**
- Un comentario como `<!-- layout: two-column -->` elige el layout

::: {.callout-tip title="Todo sigue siendo texto"}
Nunca sale de Markdown. Cada menú solo deja el texto correcto en el cursor.
:::

## El diálogo Nueva diapositiva
<!-- layout: image-caption -->

![Diapositivas ▸ Nueva diapositiva — elija un layout, escriba un título, agregue una imagen](__SHOT_NEW_SLIDE__){width=42%}

## Los layouts que puede elegir
<!-- layout: cards -->

:::: {.cards}
::: {.card}
#### Estructura
Sección · Título + viñetas · Dos columnas · Comparación · En blanco
:::
::: {.card}
#### Imágenes
Imagen + pie · A sangre · Imagen izquierda · Imagen derecha · Cita + retrato
:::
::: {.card}
#### Énfasis
Números grandes · Agenda · Tarjetas · Línea de tiempo · Cita · Código
:::
::::

## Componentes de diseño
<!-- layout: big-stat -->

:::: {.stats}
::: {.stat}
**16**

[layouts de diapositiva]{.stat-label}
:::
::: {.stat}
**9**

[temas de color]{.stat-label}
:::
::: {.stat}
**3**

[formatos de exportación]{.stat-label}
:::
::::

## Una línea de tiempo, por ejemplo
<!-- layout: timeline -->

::: {.timeline}
- **Escriba** — teclee Markdown, observe la vista previa
- **Diseñe** — elija un layout y un tema
- **Exporte** — PDF, HTML o PowerPoint
:::

## Figuras, tablas y ecuaciones
<!-- layout: two-column -->

:::: {.columns}
::: {.column width="50%"}
**Figura**

![Contenido ▸ Imagen / Figura](__SHOT_FIGURE__){width=92%}
:::
::: {.column width="50%"}
**Tabla**

![Contenido ▸ Tabla](__SHOT_TABLE__){width=88%}
:::
::::

## Las ecuaciones se renderizan con MathJax
<!-- layout: two-column -->

:::: {.columns}
::: {.column width="46%"}
![Contenido ▸ Ecuación](__SHOT_EQUATION__){width=98%}
:::
::: {.column width="54%"}
En una torre esbelta, la presión de viento gobierna:

$$ q = \tfrac{1}{2}\,\rho\,V^{2} $$

En PowerPoint, las ecuaciones se exportan como imágenes.
:::
::::

## Diagramas, dos motores
<!-- layout: two-column -->

:::: {.columns}
::: {.column width="50%"}
**Mermaid** — diagramas de flujo

```mermaid
flowchart TD
    A[Escribir] --> B[Disenar]
    B --> C[Exportar]
```
:::
::: {.column width="50%"}
**nomnoml** — estilo UML

```nomnoml
[Presentacion] -> [Diapositiva]
[Diapositiva] -> [Bloque]
```
:::
::::

::: {.notes}
Ambos motores de diagramas leen los colores del tema activo, así que un
diagrama siempre combina con la presentación. Se renderizan en HTML y PDF;
en PowerPoint caen a su texto fuente.
:::

## Temas
<!-- layout: image-caption -->

![Ver ▸ Tema cambia los nueve temas; Nuevo tema… abre el editor](__SHOT_THEME_EDITOR__){width=46%}

## Propiedades de la presentación
<!-- layout: image-caption -->

![Presentación ▸ Propiedades — título, pie, logo y marca de agua](__SHOT_PROPERTIES__){width=44%}

## El logo y la marca de agua viajan con la presentación
<!-- layout: title-content -->

- Un **logo** o **marca de agua** elegido se copia a la carpeta `figures/`
  de la presentación, para que siga siendo portable
- La marca de agua aparece tenue detrás de cada diapositiva y se estampa
  en el PDF
- La vista previa se repinta apenas acepta el diálogo

## Exportar
<!-- layout: cards -->

:::: {.cards}
::: {.card}
#### PDF
Una diapositiva por página horizontal, con metadatos y la marca de agua
estampada.
:::
::: {.card}
#### HTML
Una página web continua y desplazable — natural para compartir como enlace.
:::
::: {.card}
#### PowerPoint
Layouts estándar con los colores, fuentes y notas del orador del tema.
:::
::::

## Presentar y compartir
<!-- layout: two-column -->

:::: {.columns}
::: {.column width="50%"}
**Presentar**

- Las flechas navegan
- `S` abre las notas del orador
- `F` pasa a pantalla completa
:::
::: {.column width="50%"}
**Compartir**

- Exporte a HTML para la web
- Exporte a PDF para imprimir
- Exporte a PPTX para PowerPoint
:::
::::

## Ya está listo
<!-- layout: quote -->

> La mejor presentación es la que puede seguir editando como texto plano.
>
> — ANM Ingeniería
