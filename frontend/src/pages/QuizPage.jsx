import { useState, useEffect } from 'react'
import { getDocuments, generateQuiz, getQuizzes, getQuiz, deleteQuiz } from '../api/client'
import { QuizIcon, TrashIcon, SpinnerIcon, CheckIcon, XIcon } from '../components/Icons'

/* ─── MCQ Card ─────────────────────────────────────────── */
function MCQCard({ q, index }) {
  const [selected, setSelected] = useState(null)
  const answered = selected !== null
  const options = q.options || []
  const correctIdx = options.findIndex(opt => opt.label === q.answer)

  return (
    <div className="surface-card p-5 animate-slide-up" style={{ animationDelay: `${index * 0.05}s` }}>
      <p className="text-sm font-medium text-gray-200 mb-3">{q.question}</p>
      <div className="space-y-2">
        {options.map((opt, i) => {
          const isCorrect = i === correctIdx
          const isSelected = i === selected
          let style = 'border-dark-border text-gray-400 hover:bg-white/[0.03] hover:border-brand-500/30'
          if (answered) {
            if (isCorrect) style = 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
            else if (isSelected && !isCorrect) style = 'border-red-500/40 bg-red-500/10 text-red-300'
            else style = 'border-dark-border text-gray-600'
          }
          return (
            <button
              key={i}
              onClick={() => !answered && setSelected(i)}
              disabled={answered}
              className={`w-full text-left px-4 py-2.5 rounded-lg border text-sm transition-all duration-300 flex items-center gap-2 ${style}`}
            >
              <span className="w-5 h-5 rounded-full border border-current flex items-center justify-center text-xs shrink-0">
                {answered && isCorrect ? <CheckIcon className="w-3 h-3" /> : answered && isSelected ? <XIcon className="w-3 h-3" /> : opt.label}
              </span>
              {opt.text}
            </button>
          )
        })}
      </div>
      {answered && q.explanation && (
        <div className="mt-3 p-3 rounded-lg bg-brand-500/5 border border-brand-500/10 text-xs text-gray-400 animate-fade-in">
          {q.explanation}
        </div>
      )}
    </div>
  )
}

/* ─── Flashcard ────────────────────────────────────────── */
function FlashCard({ q, index }) {
  const [flipped, setFlipped] = useState(false)

  return (
    <div
      className="animate-slide-up cursor-pointer"
      style={{ animationDelay: `${index * 0.05}s`, perspective: '800px' }}
      onClick={() => setFlipped(f => !f)}
    >
      <div
        className="relative w-full min-h-[180px] transition-transform duration-500"
        style={{ transformStyle: 'preserve-3d', transform: flipped ? 'rotateY(180deg)' : 'rotateY(0deg)' }}
      >
        {/* Front */}
        <div
          className="absolute inset-0 surface-card p-5 flex flex-col justify-center"
          style={{ backfaceVisibility: 'hidden' }}
        >
          <p className="text-xs text-brand-400 font-medium mb-2">Question</p>
          <p className="text-sm text-gray-200">{q.front || q.question}</p>
          <p className="text-xs text-gray-600 mt-3">Click to flip →</p>
        </div>
        {/* Back */}
        <div
          className="absolute inset-0 surface-card p-5 flex flex-col justify-center bg-brand-500/5 border-brand-500/20"
          style={{ backfaceVisibility: 'hidden', transform: 'rotateY(180deg)' }}
        >
          <p className="text-xs text-emerald-400 font-medium mb-2">Answer</p>
          <p className="text-sm text-gray-200">{q.back || q.answer}</p>
          {q.explanation && <p className="text-xs text-gray-500 mt-2">{q.explanation}</p>}
        </div>
      </div>
    </div>
  )
}

/* ─── Main Page ────────────────────────────────────────── */
export default function QuizPage() {
  const [docs, setDocs] = useState([])
  const [selectedDocs, setSelectedDocs] = useState([])
  const [quizType, setQuizType] = useState('mcq')
  const [nQuestions, setNQuestions] = useState(5)
  const [generating, setGenerating] = useState(false)
  const [quizzes, setQuizzes] = useState([])
  const [activeQuiz, setActiveQuiz] = useState(null)

  useEffect(() => {
    getDocuments().then(r => setDocs(r.data.filter(d => d.status === 'ready'))).catch(() => {})
    loadQuizzes()
  }, [])

  const loadQuizzes = () => getQuizzes().then(r => setQuizzes(r.data)).catch(() => {})

  const toggleDoc = id => setSelectedDocs(prev =>
    prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
  )

  const handleGenerate = async () => {
    if (!selectedDocs.length || generating) return
    setGenerating(true)
    try {
      const res = await generateQuiz(selectedDocs, quizType, nQuestions)
      setActiveQuiz(res.data)
      loadQuizzes()
    } catch (e) {
      alert(e.response?.data?.detail || 'Failed to generate quiz')
    } finally {
      setGenerating(false)
    }
  }

  const handleLoadQuiz = async id => {
    const res = await getQuiz(id)
    setActiveQuiz(res.data)
  }

  const handleDeleteQuiz = async id => {
    await deleteQuiz(id)
    if (activeQuiz?.id === id) setActiveQuiz(null)
    loadQuizzes()
  }

  const questions = activeQuiz?.questions || []

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-6 animate-fade-in">
      <div>
        <h1 className="text-xl font-semibold text-gray-100">Quiz generator</h1>
        <p className="text-sm text-gray-500 mt-1">Test your knowledge with AI-generated questions from your docs</p>
      </div>

      {/* Generate controls */}
      <div className="surface-card p-5 space-y-4">
        {/* Doc selector */}
        <div>
          <p className="text-sm font-medium text-gray-300 mb-2">Select documents</p>
          {docs.length === 0 ? (
            <p className="text-xs text-gray-500">No documents available — upload some first</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {docs.map(d => (
                <button
                  key={d.id}
                  onClick={() => toggleDoc(d.id)}
                  className={`text-xs px-3 py-1.5 rounded-full border transition-all duration-200 ${
                    selectedDocs.includes(d.id)
                      ? 'border-brand-500/40 bg-brand-500/10 text-brand-300'
                      : 'border-dark-border text-gray-500 hover:border-brand-500/20 hover:text-gray-400'
                  }`}
                >
                  {d.filename}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Quiz type + count */}
        <div className="flex gap-4">
          <div className="flex-1">
            <p className="text-xs text-gray-500 mb-1.5 font-medium">Type</p>
            <div className="flex gap-2">
              {['mcq', 'flashcard'].map(t => (
                <button
                  key={t}
                  onClick={() => setQuizType(t)}
                  className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-all border ${
                    quizType === t
                      ? 'border-brand-500/40 bg-brand-500/10 text-brand-300'
                      : 'border-dark-border text-gray-500 hover:bg-white/[0.03]'
                  }`}
                >
                  {t.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
          <div>
            <p className="text-xs text-gray-500 mb-1.5 font-medium">Questions</p>
            <input
              type="number"
              min={1}
              max={20}
              value={nQuestions}
              onChange={e => setNQuestions(Number(e.target.value))}
              className="input-field w-20 text-center"
            />
          </div>
        </div>

        <button
          onClick={handleGenerate}
          disabled={generating || !selectedDocs.length}
          className="btn-primary w-full"
        >
          {generating ? <><SpinnerIcon className="w-4 h-4" /> Generating…</> : <><QuizIcon className="w-4 h-4" /> Generate quiz</>}
        </button>
      </div>

      {/* Active quiz */}
      {activeQuiz && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm font-medium text-gray-300">
              {activeQuiz.quiz_type === 'mcq' ? 'Multiple Choice' : 'Flashcards'} — {questions.length} questions
            </p>
          </div>
          <div className="space-y-3">
            {questions.map((q, i) =>
              activeQuiz.quiz_type === 'flashcard'
                ? <FlashCard key={i} q={q} index={i} />
                : <MCQCard key={i} q={q} index={i} />
            )}
          </div>
        </div>
      )}

      {/* Quiz history */}
      {quizzes.length > 0 && (
        <div>
          <p className="text-sm font-medium text-gray-300 mb-3">Past quizzes</p>
          <div className="surface-card divide-y divide-dark-border">
            {quizzes.map(q => (
              <div key={q.id} className="flex items-center gap-3 px-4 py-3 group hover:bg-white/[0.02] transition-colors">
                <div className="flex-1 min-w-0">
                  <button
                    onClick={() => handleLoadQuiz(q.id)}
                    className="text-sm text-gray-300 hover:text-brand-400 transition-colors truncate"
                  >
                    {q.quiz_type?.toUpperCase()} · {q.question_count} questions · {new Date(q.created_at).toLocaleDateString()}
                  </button>
                </div>
                <button
                  onClick={() => handleDeleteQuiz(q.id)}
                  className="text-gray-600 hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100"
                >
                  <TrashIcon className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
