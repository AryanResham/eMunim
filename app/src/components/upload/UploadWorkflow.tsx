import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { StepIndicator } from './StepIndicator'
import { Step1Upload } from './Step1Upload'
import { Step2Classify } from './Step2Classify'
import { Step3Extract } from './Step3Extract'
import { Step4Validate } from './Step4Validate'
import { classifyDocument, extractFields, validateEntry } from '@/api/mockBackend'
import type { WorkflowState, ClassificationResult } from '@/types/upload'

const INITIAL_STATE: WorkflowState = {
  step: 1,
  direction: 1,
  file: null,
  filePreviewUrl: null,
  classification: null,
  extractedFields: null,
  validationResult: null,
  isProcessing: false,
}

const stepVariants = {
  enter: (d: number) => ({ opacity: 0, x: d * 48 }),
  center: { opacity: 1, x: 0 },
  exit: (d: number) => ({ opacity: 0, x: d * -48 }),
}

export function UploadWorkflow() {
  const [state, setState] = useState<WorkflowState>(INITIAL_STATE)

  function go(step: 1 | 2 | 3 | 4, direction: 1 | -1) {
    setState((s) => ({ ...s, step, direction }))
  }

  // Step 1 → 2
  async function handleFileReady(file: File) {
    const previewUrl = file.type.startsWith('image/') ? URL.createObjectURL(file) : null
    setState((s) => ({ ...s, file, filePreviewUrl: previewUrl, isProcessing: true }))
    const classification = await classifyDocument(file)
    setState((s) => ({ ...s, classification, isProcessing: false }))
    go(2, 1)
  }

  // Step 2 → 3
  async function handleClassifyProceed(updated: ClassificationResult) {
    setState((s) => ({ ...s, classification: updated, isProcessing: true }))
    const extractedFields = await extractFields(updated)
    setState((s) => ({ ...s, extractedFields, isProcessing: false }))
    go(3, 1)
  }

  // Step 3 → 4
  async function handleExtractProceed() {
    if (!state.extractedFields) return
    setState((s) => ({ ...s, isProcessing: true }))
    const validationResult = await validateEntry(state.extractedFields)
    setState((s) => ({ ...s, validationResult, isProcessing: false }))
    go(4, 1)
  }

  // Step 4 → done (reset)
  function handleSubmit() {
    setTimeout(() => {
      if (state.filePreviewUrl) URL.revokeObjectURL(state.filePreviewUrl)
      setState(INITIAL_STATE)
    }, 1200)
  }

  return (
    <div className="flex flex-col h-full w-full">
      <StepIndicator currentStep={state.step} />

      <div className="flex-1 overflow-hidden relative">
        <AnimatePresence mode="wait" custom={state.direction}>
          <motion.div
            key={state.step}
            custom={state.direction}
            variants={stepVariants}
            initial="enter"
            animate="center"
            exit="exit"
            transition={{ duration: 0.22, ease: [0.4, 0, 0.2, 1] }}
            className="absolute inset-0 overflow-y-auto px-1 pb-4"
          >
            {state.step === 1 && (
              <Step1Upload
                onFileReady={handleFileReady}
                isProcessing={state.isProcessing}
              />
            )}

            {state.step === 2 && state.file && state.classification && (
              <Step2Classify
                file={state.file}
                filePreviewUrl={state.filePreviewUrl}
                classification={state.classification}
                onProceed={handleClassifyProceed}
                onBack={() => go(1, -1)}
                isProcessing={state.isProcessing}
              />
            )}

            {state.step === 3 && state.file && state.classification && (
              <Step3Extract
                file={state.file}
                filePreviewUrl={state.filePreviewUrl}
                classification={state.classification}
                fields={state.extractedFields ?? []}
                onProceed={handleExtractProceed}
                onBack={() => go(2, -1)}
                isProcessing={state.isProcessing}
              />
            )}

            {state.step === 4 && state.extractedFields && state.validationResult && (
              <Step4Validate
                fields={state.extractedFields}
                validationResult={state.validationResult}
                onSubmit={handleSubmit}
                onBack={() => go(3, -1)}
                isProcessing={state.isProcessing}
              />
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  )
}
