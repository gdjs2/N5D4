import { useEffect, useMemo, useRef, useState } from 'react'
import { BookOpen } from 'lucide-react'
import { FaGithub } from 'react-icons/fa'
import ReactMarkdown from 'react-markdown'
import rehypeKatex from 'rehype-katex'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import 'katex/dist/katex.min.css'
import documentationMd from './content/documentation.md?raw'
import './App.css'

function slugify(value) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '')
}

function parseDocumentationSections(markdown) {
  const lines = markdown.split('\n')
  const sections = []

  let title = 'Documentation'
  let currentTitle = null
  let currentLines = []
  const preface = []

  for (const line of lines) {
    if (line.startsWith('# ') && title === 'Documentation') {
      title = line.slice(2).trim()
      continue
    }

    if (line.startsWith('## ')) {
      if (currentTitle) {
        sections.push({
          title: currentTitle,
          slug: slugify(currentTitle),
          markdown: `## ${currentTitle}\n\n${currentLines.join('\n').trim()}`,
        })
      }
      currentTitle = line.slice(3).trim()
      currentLines = []
      continue
    }

    if (currentTitle) {
      currentLines.push(line)
    } else {
      preface.push(line)
    }
  }

  if (currentTitle) {
    sections.push({
      title: currentTitle,
      slug: slugify(currentTitle),
      markdown: `## ${currentTitle}\n\n${currentLines.join('\n').trim()}`,
    })
  }

  const introText = preface.join('\n').trim()
  if (introText) {
    const existingIntroIndex = sections.findIndex(
      (section) => section.slug === 'introduction' || section.title.toLowerCase() === 'introduction',
    )

    if (existingIntroIndex >= 0) {
      const existing = sections[existingIntroIndex]
      const existingBody = existing.markdown.replace(/^##\s+.*\n\n?/, '')
      sections[existingIntroIndex] = {
        ...existing,
        markdown: `## Introduction\n\n${introText}\n\n${existingBody}`.trim(),
      }
    } else {
      sections.unshift({
        title: 'Introduction',
        slug: 'introduction',
        markdown: `## Introduction\n\n${introText}`,
      })
    }
  }

  return { title, sections }
}

function AssemblyComparePanel({ beforeHtml, afterHtml }) {
  const panelRef = useRef(null)
  const [split, setSplit] = useState(50)
  const [isDragging, setIsDragging] = useState(false)
  const [autoPlayEnabled, setAutoPlayEnabled] = useState(true)

  useEffect(() => {
    if (isDragging || !autoPlayEnabled) {
      return undefined
    }

    const sequence = [
      { value: 53, delay: 280 },
      { value: 55, delay: 280 },
      { value: 50, delay: 320 },
      { value: 53, delay: 280 },
      { value: 50, delay: 320 },
      { value: 1, delay: 1500 },
      // { value: 50, delay: 520 },
      { value: 50, delay: 1200 },
    ]

    let index = 0
    let timerId

    const step = () => {
      if (index >= sequence.length) {
        setAutoPlayEnabled(false)
        return
      }

      const current = sequence[index]
      setSplit(current.value)
      index += 1
      timerId = window.setTimeout(step, current.delay)
    }

    timerId = window.setTimeout(step, 900)

    return () => {
      window.clearTimeout(timerId)
    }
  }, [isDragging, autoPlayEnabled])

  const updateSplitByClientX = (clientX) => {
    if (!panelRef.current) {
      return
    }

    const rect = panelRef.current.getBoundingClientRect()
    const clampedX = Math.max(rect.left, Math.min(clientX, rect.right))
    const nextSplit = ((clampedX - rect.left) / rect.width) * 100
    setSplit(nextSplit)
  }

  const handlePointerDown = (event) => {
    event.preventDefault()
    setAutoPlayEnabled(false)
    setIsDragging(true)
    event.currentTarget.setPointerCapture(event.pointerId)
    updateSplitByClientX(event.clientX)
  }

  const handlePointerMove = (event) => {
    if (!isDragging) {
      return
    }
    event.preventDefault()
    updateSplitByClientX(event.clientX)
  }

  const handlePointerUp = (event) => {
    setIsDragging(false)
    event.currentTarget.releasePointerCapture(event.pointerId)
  }

  return (
    <article className="comparisonPanel">
      <div className="labels">
        <span>Before N5D4</span>
        <span>After N5D4</span>
      </div>

      <div
        ref={panelRef}
        className={`codeCompare ${isDragging ? 'dragging' : ''}`}
        style={{ '--split': `${split}%` }}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
      >
        <pre className="codeLayer codeBefore" aria-label="Before N5D4 disassembly code">
          <code
            draggable="false"
            dangerouslySetInnerHTML={{ __html: beforeHtml }}
          />
        </pre>
        <pre className="codeLayer codeAfter" aria-label="After N5D4 disassembly code">
          <code
            draggable="false"
            dangerouslySetInnerHTML={{ __html: afterHtml }}
          />
        </pre>
        <div className="divider" aria-hidden="true">
          <span className="dividerHandle" />
        </div>
      </div>
    </article>
  )
}

function App() {
  const getRouteStateFromHash = () => {
    const match = window.location.hash.match(/^#\/documentation(?:\/([^/?#]+))?$/)
    if (match) {
      return {
        route: 'documentation',
        sectionSlug: match[1] ?? '',
      }
    }

    return {
      route: 'home',
      sectionSlug: '',
    }
  }

  const [routeState, setRouteState] = useState(getRouteStateFromHash)

  const documentationData = useMemo(
    () => parseDocumentationSections(documentationMd),
    [],
  )

  const activeDocSection = useMemo(() => {
    if (documentationData.sections.length === 0) {
      return null
    }

    return (
      documentationData.sections.find((section) => section.slug === routeState.sectionSlug)
      ?? documentationData.sections[0]
    )
  }, [documentationData.sections, routeState.sectionSlug])

  useEffect(() => {
    const onHashChange = () => {
      setRouteState(getRouteStateFromHash())
    }

    window.addEventListener('hashchange', onHashChange)
    return () => {
      window.removeEventListener('hashchange', onHashChange)
    }
  }, [])

  const beforeSliceA = useMemo(
    () => [
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015c74</span>  <span class="bytes">06f19f97</span>  <span class="mnemonic">ldrls</span>  <span class="operand">pc,[pc,r6,lsl #0x2]=>PTR_LAB_00015c7c</span>  <span class="xrefNote">; XREF: 00015c74(*)</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015c78</span>  <span class="bytes">910000ea</span>  <span class="mnemonic">b</span>      <span class="operand">LAB_00015ec4</span></span>',
      '<span class="line"><span class="label">PTR_LAB_00015c7c:</span> <span class="xrefNote">; jump table</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015c7c</span>  <span class="bytes">f05c0100</span>  <span class="mnemonic">addr</span>   <span class="operand">LAB_00015cf0</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015c80</span>  <span class="bytes">685d0100</span>  <span class="mnemonic">addr</span>   <span class="operand">DAT_00015d68</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015c84</span>  <span class="bytes">845d0100</span>  <span class="mnemonic">addr</span>   <span class="operand">DAT_00015d84</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015c88</span>  <span class="bytes">a85d0100</span>  <span class="mnemonic">addr</span>   <span class="operand">DAT_00015da8</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015c8c</span>  <span class="bytes">d45d0100</span>  <span class="mnemonic">addr</span>   <span class="operand">LAB_00015dd4</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015c90</span>  <span class="bytes">045e0100</span>  <span class="mnemonic">addr</span>   <span class="operand">LAB_00015e04</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015c94</span>  <span class="bytes">3c5e0100</span>  <span class="mnemonic">addr</span>   <span class="operand">LAB_00015e3c</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015c98</span>  <span class="bytes">7c5e0100</span>  <span class="mnemonic">addr</span>   <span class="operand">LAB_00015e7c</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015c9c</span>  <span class="bytes">a45c0100</span>  <span class="mnemonic">addr</span>   <span class="operand">LAB_00015ca4</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015ca0</span>  <span class="bytes">105d0100</span>  <span class="mnemonic">addr</span>   <span class="operand">LAB_00015d10</span></span>',
      '<span class="line"><span class="label">LAB_00015ca4:</span> <span class="xrefNote">; XREF: 00015c9c(*)</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015ca4</span>  <span class="bytes">142085e2</span>  <span class="mnemonic">add</span>    <span class="operand">r2,r5,#0x14</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015ca8</span>  <span class="bytes">0c0092e8</span>  <span class="mnemonic">ldmia</span>  <span class="operand">r2,{r2,r3}</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015cac</span>  <span class="bytes">1c1095e5</span>  <span class="mnemonic">ldr</span>    <span class="operand">r1,[r5,#0x1c]</span></span>',
      '<span class="line"><span class="comment">...</span></span>',
      '<span class="line"><span class="label">DAT_00015d68:</span> <span class="xrefNote">; XREF: 00015c80(*)</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015d68</span>  <span class="bytes">01</span>        <span class="mnemonic">??</span>     <span class="operand">01h</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015d69</span>  <span class="bytes">10</span>        <span class="mnemonic">??</span>     <span class="operand">10h</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015d6a</span>  <span class="bytes">a0</span>        <span class="mnemonic">??</span>     <span class="operand">A0h</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015d6b</span>  <span class="bytes">e3</span>        <span class="mnemonic">??</span>     <span class="operand">E3h</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015d6c</span>  <span class="bytes">04</span>        <span class="mnemonic">??</span>     <span class="operand">04h</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015d6d</span>  <span class="bytes">00</span>        <span class="mnemonic">??</span>     <span class="operand">00h</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015d6e</span>  <span class="bytes">a0</span>        <span class="mnemonic">??</span>     <span class="operand">A0h</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015d6f</span>  <span class="bytes">e1</span>        <span class="mnemonic">??</span>     <span class="operand">E1h</span></span>',
    ].join('\n'),
    [],
  )

  const refinedSliceA = useMemo(
    () => [
      '<span class="line"><span class="label">switchD:</span> <span class="xrefNote">; FWD[11]: 00015c7c, 00015ca4, 00015cf0, 00015d10, 00015d68...</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015c74</span>  <span class="bytes">06f19f97</span>  <span class="mnemonic">ldrls</span>  <span class="operand">pc,[pc,r6,lsl #0x2]=>switchdataD_00015c7c</span> <span class="comment">; = 00015cf0</span></span>',
      '<span class="line"><span class="label">default:</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015c78</span>  <span class="bytes">910000ea</span>  <span class="mnemonic">b</span>      <span class="operand">LAB_00015ec4</span></span>',
      '<span class="line"><span class="label">switchdataD_00015c7c:</span> <span class="xrefNote">; XREF[1]: 00015c74(*)</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015c7c</span>  <span class="bytes">f05c0100</span>  <span class="mnemonic">addr</span>   <span class="operand">switchD_00015c74::caseD_0</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015c80</span>  <span class="bytes">685d0100</span>  <span class="mnemonic">addr</span>   <span class="operand">switchD_00015c74::caseD_1</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015c84</span>  <span class="bytes">845d0100</span>  <span class="mnemonic">addr</span>   <span class="operand">switchD_00015c74::caseD_2</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015c88</span>  <span class="bytes">a85d0100</span>  <span class="mnemonic">addr</span>   <span class="operand">switchD_00015c74::caseD_3</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015c8c</span>  <span class="bytes">d45d0100</span>  <span class="mnemonic">addr</span>   <span class="operand">switchD_00015c74::caseD_4</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015c90</span>  <span class="bytes">045e0100</span>  <span class="mnemonic">addr</span>   <span class="operand">switchD_00015c74::caseD_5</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015c94</span>  <span class="bytes">3c5e0100</span>  <span class="mnemonic">addr</span>   <span class="operand">switchD_00015c74::caseD_6</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015c98</span>  <span class="bytes">7c5e0100</span>  <span class="mnemonic">addr</span>   <span class="operand">switchD_00015c74::caseD_7</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015c9c</span>  <span class="bytes">a45c0100</span>  <span class="mnemonic">addr</span>   <span class="operand">switchD_00015c74::caseD_8</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015ca0</span>  <span class="bytes">105d0100</span>  <span class="mnemonic">addr</span>   <span class="operand">switchD_00015c74::caseD_9</span></span>',
      '<span class="line"><span class="label">caseD_8:</span> <span class="xrefNote">; XREF[2]: 00015c74(j), 00015c9c(*)</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015ca4</span>  <span class="bytes">142085e2</span>  <span class="mnemonic">add</span>    <span class="operand">r2,r5,#0x14</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015ca8</span>  <span class="bytes">0c0092e8</span>  <span class="mnemonic">ldmia</span>  <span class="operand">r2,{r2,r3}</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015cac</span>  <span class="bytes">1c1095e5</span>  <span class="mnemonic">ldr</span>    <span class="operand">r1,[r5,#0x1c]</span></span>',
      '<span class="line"><span class="comment">...</span></span>',
      '<span class="line"><span class="label">caseD_1:</span> <span class="comment">; N5D4 Redisassembled Code Block (confidence: 0.74)</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015d68</span>  <span class="bytes">0110a0e3</span>  <span class="mnemonic">mov</span>    <span class="operand">r1,#0x1</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015d6c</span>  <span class="bytes">0400a0e1</span>  <span class="mnemonic">mov</span>    <span class="operand">r0,r4</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015d70</span>  <span class="bytes">003095e5</span>  <span class="mnemonic">ldr</span>    <span class="operand">r3,[r5,#0x0]</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015d74</span>  <span class="bytes">c4219fe5</span>  <span class="mnemonic">ldr</span>    <span class="operand">r2,[PTR_s_Written_by]</span> <span class="comment">; "Written by %s.\\n"</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015d78</span>  <span class="bytes">20d08de2</span>  <span class="mnemonic">add</span>    <span class="operand">sp,sp,#0x20</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015d7c</span>  <span class="bytes">7040bde8</span>  <span class="mnemonic">ldmia</span>  <span class="operand">sp!,{r4,r5,r6,lr}</span></span>',
      '<span class="line"><span class="segment">.text:</span><span class="addr">00015d80</span>  <span class="bytes">11edffea</span>  <span class="mnemonic">b</span>      <span class="operand">.plt::__fprintf_chk</span></span>',
    ].join('\n'),
    [],
  )

  return (
    routeState.route === 'documentation' ? (
      <div className="site">
        <section className="hero">
          <p className="kicker">Neurosymbolic Disassembly</p>
          <h1>{documentationData.title}</h1>
          <p className="subtitle">
            Navigate sections from the left sidebar. Each page displays one section from markdown.
          </p>
        </section>

        <main className="docPage docLayout">
          <aside className="docSidebar">
            <nav className="docNav" aria-label="Documentation sections">
              {documentationData.sections.map((section) => (
                <a
                  key={section.slug}
                  href={`#/documentation/${section.slug}`}
                  className={`docNavLink ${activeDocSection?.slug === section.slug ? 'active' : ''}`}
                >
                  {section.title}
                </a>
              ))}
            </nav>
          </aside>

          <article className="docMarkdown docContentPane">
            <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}>
              {activeDocSection?.markdown ?? 'No section available.'}
            </ReactMarkdown>
          </article>
        </main>

        <div className="bottomActions">
          <a className="actionButton" href="#/">Back Home</a>
          <a className="actionButton" href="https://github.com" target="_blank" rel="noreferrer"><FaGithub size={17} />GitHub</a>
        </div>
      </div>
    ) : (
    <div className="site">
      <section className="hero">
        <p className="kicker">Neurosymbolic Disassembly</p>
        <h1>N5D4 Disassembler</h1>
        <p className="subtitle">
          N5D4 is a neurosymbolic disassembly refinement tool for Ghidra. It combines neural
          prediction with logic constraints to identify likely code regions and redisassemble
          ambiguous blocks into higher-quality analysis results.
        </p>
      </section>

      <section className="sliderSection" aria-label="Assembly comparison">
        <AssemblyComparePanel
          beforeHtml={beforeSliceA}
          afterHtml={refinedSliceA}
        />
      </section>

      <div className="bottomActions">
        <a className="actionButton" href="#/documentation/introduction"><BookOpen size={17} strokeWidth={2} />Documentation</a>
        <a className="actionButton" href="https://github.com" target="_blank" rel="noreferrer"><FaGithub size={17} />GitHub</a>
      </div>
    </div>
    )
  )
}

export default App
