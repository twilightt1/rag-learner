import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import 'katex/dist/katex.min.css'

export function MarkdownRenderer({ content }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkMath]}
      rehypePlugins={[rehypeKatex]}
      components={{
        // Ensure math blocks are centered and scrollable if too wide
        div: ({ node, ...props }) => {
          const isMathDisplay = node.properties?.className?.includes('math-display')
          if (isMathDisplay) {
            return <div className='overflow-x-auto py-2' {...props} />
          }
          return <div {...props} />
        },
        p: ({ node, ...props }) => <p className='mb-2 last:mb-0' {...props} />,
        code: ({ node, inline, className, children, ...props }) => {
          const match = /language-(\w+)/.exec(className || '')
          return !inline && match ? (
            <pre className='bg-dark-elevated p-3 rounded-lg overflow-x-auto text-sm my-2 border border-dark-border'>
              <code className={className} {...props}>
                {children}
              </code>
            </pre>
          ) : (
            <code
              className='bg-dark-elevated px-1.5 py-0.5 rounded text-sm font-mono text-brand-300 border border-dark-border/50'
              {...props}
            >
              {children}
            </code>
          )
        },
      }}
    >
      {content}
    </ReactMarkdown>
  )
}
