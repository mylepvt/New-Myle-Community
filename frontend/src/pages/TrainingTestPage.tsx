import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Label } from '@/components/ui/label'
import { CheckCircle, XCircle, Clock, Award } from 'lucide-react'
import { useTrainingTestQuestionsQuery, useSubmitTrainingTestMutation } from '@/hooks/use-training-query'
import { useAuthMeQuery } from '@/hooks/use-auth-me-query'

type TestResult = {
  passed: boolean
  score: number
  total_questions: number
  percent: number
  pass_mark_percent: number
}

export default function TrainingTestPage() {
  const { data: questions, isLoading: questionsLoading } = useTrainingTestQuestionsQuery()
  const { data: authData } = useAuthMeQuery()
  const submitMutation = useSubmitTrainingTestMutation()
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [showResults, setShowResults] = useState(false)
  const [results, setResults] = useState<TestResult | null>(null)

  const canTakeTest = authData?.training_status === 'completed' || !authData?.training_required

  const handleAnswerChange = (questionId: string, answer: string) => {
    setAnswers(prev => ({
      ...prev,
      [questionId]: answer
    }))
  }

  const handleSubmitTest = async () => {
    if (Object.keys(answers).length !== questions?.length) {
      alert('Please answer all questions before submitting.')
      return
    }

    try {
      const result = await submitMutation.mutateAsync(answers)
      setResults(result)
      setShowResults(true)
    } catch (error) {
      console.error('Failed to submit test:', error)
    }
  }

  const handleRetakeTest = () => {
    setAnswers({})
    setShowResults(false)
    setResults(null)
  }

  if (questionsLoading) {
    return <div className="flex justify-center p-8">Loading test questions...</div>
  }

  if (!canTakeTest) {
    return (
      <div className="container mx-auto p-6">
        <Card className="max-w-2xl mx-auto">
          <CardHeader className="text-center">
            <Clock className="w-16 h-16 mx-auto text-yellow-600 mb-4" />
            <CardTitle className="text-2xl">Test Not Available</CardTitle>
            <CardDescription>
              You must complete all training days before taking the certification test.
            </CardDescription>
          </CardHeader>
          <CardContent className="text-center">
            <Button onClick={() => window.history.back()}>
              Back to Training
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (showResults && results) {
    return (
      <div className="container mx-auto p-6">
        <Card className="max-w-2xl mx-auto">
          <CardHeader className="text-center">
            {results.passed ? (
              <CheckCircle className="w-16 h-16 mx-auto text-green-600 mb-4" />
            ) : (
              <XCircle className="w-16 h-16 mx-auto text-red-600 mb-4" />
            )}
            <CardTitle className="text-2xl">
              {results.passed ? 'Congratulations!' : 'Test Not Passed'}
            </CardTitle>
            <CardDescription>
              {results.passed 
                ? 'You have successfully passed the certification test!'
                : 'You did not meet the passing score. Please try again.'
              }
            </CardDescription>
          </CardHeader>
          
          <CardContent className="space-y-6">
            <div className="text-center">
              <div className="text-4xl font-bold mb-2">
                {results.score} / {results.total_questions}
              </div>
              <div className="text-xl text-gray-600">
                {results.percent}% - Pass mark: {results.pass_mark_percent}%
              </div>
            </div>

            {results.passed && (
              <Alert className="bg-green-50 border-green-200">
                <Award className="w-4 h-4" />
                <AlertDescription className="text-green-800">
                  Your training is now complete! You can download your certificate from your profile.
                </AlertDescription>
              </Alert>
            )}

            {!results.passed && (
              <Alert className="bg-red-50 border-red-200">
                <XCircle className="w-4 h-4" />
                <AlertDescription className="text-red-800">
                  You need at least {results.pass_mark_percent}% to pass. Review the training materials and try again.
                </AlertDescription>
              </Alert>
            )}

            <div className="flex justify-center space-x-4">
              {!results.passed && (
                <Button onClick={handleRetakeTest}>
                  Retake Test
                </Button>
              )}
              <Button variant="outline" onClick={() => window.history.back()}>
                Back to Training
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="container mx-auto p-6">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Training Certification Test</h1>
        <p className="text-gray-600">
          Answer all questions to complete your certification. Passing score: {60}%
        </p>
        
        <div className="mt-4 p-4 bg-blue-50 rounded-lg">
          <div className="flex items-center justify-between">
            <span className="text-blue-800 font-medium">Progress</span>
            <span className="text-blue-600">
              {Object.keys(answers).length} / {questions?.length || 0} questions answered
            </span>
          </div>
          <div className="w-full bg-blue-200 rounded-full h-2 mt-2">
            <div 
              className="bg-blue-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${(Object.keys(answers).length / (questions?.length || 1)) * 100}%` }}
            />
          </div>
        </div>
      </div>

      <div className="space-y-6">
        {questions?.map((question, index) => (
          <Card key={question.id}>
            <CardHeader>
              <CardTitle className="flex items-start space-x-3">
                <Badge variant="outline" className="mt-1">
                  {index + 1}
                </Badge>
                <span className="text-lg">{question.question}</span>
              </CardTitle>
            </CardHeader>
            
            <CardContent>
              <RadioGroup
                value={answers[question.id.toString()] || ''}
                onValueChange={(value) => handleAnswerChange(question.id.toString(), value)}
              >
                <div className="space-y-3">
                  {Object.entries(question.options).map(([option, text]) => (
                    <div key={option} className="flex items-center space-x-2">
                      <RadioGroupItem value={option} id={`${question.id}-${option}`} />
                      <Label 
                        htmlFor={`${question.id}-${option}`}
                        className="flex-1 cursor-pointer"
                      >
                        <span className="font-medium mr-2">{option.toUpperCase()}.</span>
                        {text}
                      </Label>
                    </div>
                  ))}
                </div>
              </RadioGroup>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="mt-8 flex justify-center">
        <Button 
          size="lg"
          onClick={handleSubmitTest}
          disabled={submitMutation.isPending || Object.keys(answers).length !== questions?.length}
        >
          {submitMutation.isPending ? 'Submitting...' : 'Submit Test'}
        </Button>
      </div>
    </div>
  )
}
