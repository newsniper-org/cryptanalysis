// YSC5 사양서 공통 템플릿
//
// 한글(Hangul) 본문 + 영문/수학 혼용. Noto Sans CJK KR + STIX-Two-Math 기반.
// Typst >= 0.14.

#let spec(
  title: none,
  subtitle: none,
  authors: (),
  version: "v0.1-draft",
  date: datetime.today(),
  body,
) = {
  // ---------- 페이지 ----------
  set page(
    paper: "a4",
    margin: (x: 2.2cm, top: 2.4cm, bottom: 2.4cm),
    numbering: "1 / 1",
    number-align: center,
  )

  // ---------- 본문 폰트 ----------
  set text(
    font: ("New Computer Modern", "Noto Sans CJK KR"),
    lang: "ko",
    size: 10.5pt,
    fallback: true,
  )
  show raw: set text(font: ("DejaVu Sans Mono", "Noto Sans CJK KR"), size: 9pt)

  // ---------- 수식 ----------
  set math.equation(numbering: "(1)")
  show math.equation: set text(font: ("New Computer Modern Math", "Noto Sans CJK KR"))

  // ---------- 헤딩 ----------
  set heading(numbering: "1.1.")
  show heading.where(level: 1): it => {
    pagebreak(weak: true)
    block(above: 1.2em, below: 0.8em)[
      #set text(size: 17pt, weight: "bold")
      #it
    ]
  }
  show heading.where(level: 2): it => block(above: 1em, below: 0.5em)[
    #set text(size: 13pt, weight: "bold")
    #it
  ]
  show heading.where(level: 3): it => block(above: 0.8em, below: 0.4em)[
    #set text(size: 11.5pt, weight: "bold")
    #it
  ]

  // ---------- 표 ----------
  set table(
    inset: (x: 8pt, y: 5pt),
    stroke: 0.5pt,
  )
  show table.cell.where(y: 0): set text(weight: "bold")

  // ---------- 단락 ----------
  set par(justify: true, leading: 0.65em, first-line-indent: 0em)
  show link: set text(fill: rgb("#1f4e8e"))

  // ---------- 타이틀 페이지 ----------
  align(center + horizon)[
    #block[
      #text(size: 24pt, weight: "bold")[#title]
      #if subtitle != none [
        \
        #v(0.4em)
        #text(size: 14pt)[#subtitle]
      ]
    ]
    #v(2em)
    #text(size: 11pt)[
      #if authors != () [
        #authors.join(", ") \
      ]
      #version  ·  #date.display("[year]-[month]-[day]")
    ]
  ]

  pagebreak()

  // ---------- 목차 ----------
  outline(title: [목차], depth: 2, indent: 1em)
  pagebreak()

  // ---------- 본문 ----------
  counter(page).update(1)
  body
}

// ---------- 정의·정리 환경 ----------
#let definition(name, body) = block(
  fill: rgb("#f4f6fa"),
  inset: 10pt,
  radius: 3pt,
  width: 100%,
)[*정의 (#name).* #body]

#let theorem(name, body) = block(
  fill: rgb("#eef7ee"),
  inset: 10pt,
  radius: 3pt,
  width: 100%,
)[*정리 (#name).* #body]

#let remark(body) = block(
  fill: rgb("#fff9e6"),
  inset: 10pt,
  radius: 3pt,
  width: 100%,
)[*비고.* #body]

#let verified(body) = block(
  fill: rgb("#e8f4fd"),
  inset: 10pt,
  radius: 3pt,
  width: 100%,
  stroke: (left: 2pt + rgb("#1f4e8e")),
)[*Isabelle/HOL 기계 검증.* #body]

// ---------- 코드 라벨 ----------
#let algo(name, body) = block(
  fill: rgb("#fafafa"),
  inset: 10pt,
  radius: 3pt,
  stroke: 0.5pt + rgb("#cccccc"),
  width: 100%,
)[
  *알고리즘 (#name)*
  #v(0.3em)
  #body
]
