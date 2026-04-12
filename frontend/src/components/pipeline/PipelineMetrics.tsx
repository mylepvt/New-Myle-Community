import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { 
  TrendingUp, 
  Users, 
  DollarSign, 
  Calendar,
  Target,
  Activity
} from 'lucide-react'
import type { PipelineMetrics } from '@/hooks/use-pipeline-query'

interface PipelineMetricsProps {
  metrics: PipelineMetrics
}

export default function PipelineMetrics({ metrics }: PipelineMetricsProps) {
  const getRateColor = (rate: number) => {
    if (rate >= 70) return 'text-green-600'
    if (rate >= 50) return 'text-yellow-600'
    return 'text-red-600'
  }

  const getRateBadgeVariant = (rate: number) => {
    if (rate >= 70) return 'success'
    if (rate >= 50) return 'warning'
    return 'danger'
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* Total Leads */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Total Leads</CardTitle>
          <Users className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{metrics.total_leads}</div>
          <p className="text-xs text-muted-foreground">
            {metrics.period}
          </p>
        </CardContent>
      </Card>

      {/* Conversion Rate */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Conversion Rate</CardTitle>
          <TrendingUp className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className={`text-2xl font-bold ${getRateColor(metrics.conversion_rate)}`}>
            {metrics.conversion_rate}%
          </div>
          <p className="text-xs text-muted-foreground">
            <Badge variant={getRateBadgeVariant(metrics.conversion_rate) as any}>
              {metrics.conversion_rate >= 70 ? 'Excellent' : 
               metrics.conversion_rate >= 50 ? 'Good' : 'Needs Work'}
            </Badge>
          </p>
        </CardContent>
      </Card>

      {/* Payment Rate */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Payment Rate</CardTitle>
          <DollarSign className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className={`text-2xl font-bold ${getRateColor(metrics.payment_rate)}`}>
            {metrics.payment_rate}%
          </div>
          <p className="text-xs text-muted-foreground">
            {metrics.funnel.paid} paid leads
          </p>
        </CardContent>
      </Card>

      {/* Day 2 Rate */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Day 2 Rate</CardTitle>
          <Calendar className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className={`text-2xl font-bold ${getRateColor(metrics.day2_rate)}`}>
            {metrics.day2_rate}%
          </div>
          <p className="text-xs text-muted-foreground">
            {metrics.funnel.day2} completed Day 2
          </p>
        </CardContent>
      </Card>

      {/* Funnel Overview */}
      <Card className="md:col-span-2 lg:col-span-4">
        <CardHeader>
          <CardTitle className="text-lg flex items-center">
            <Activity className="w-5 h-5 mr-2" />
            Conversion Funnel
          </CardTitle>
          <CardDescription>
            Lead progression through pipeline stages
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <div className="text-center">
              <div className="text-lg font-semibold text-blue-600">
                {metrics.funnel.new_leads}
              </div>
              <div className="text-xs text-gray-600">New Leads</div>
            </div>
            <div className="text-center">
              <div className="text-lg font-semibold text-yellow-600">
                {metrics.funnel.contacted}
              </div>
              <div className="text-xs text-gray-600">Contacted</div>
            </div>
            <div className="text-center">
              <div className="text-lg font-semibold text-green-600">
                {metrics.funnel.paid}
              </div>
              <div className="text-xs text-gray-600">Paid</div>
            </div>
            <div className="text-center">
              <div className="text-lg font-semibold text-orange-600">
                {metrics.funnel.day1}
              </div>
              <div className="text-xs text-gray-600">Day 1</div>
            </div>
            <div className="text-center">
              <div className="text-lg font-semibold text-red-600">
                {metrics.funnel.day2}
              </div>
              <div className="text-xs text-gray-600">Day 2</div>
            </div>
            <div className="text-center">
              <div className="text-lg font-semibold text-emerald-600">
                {metrics.funnel.converted}
              </div>
              <div className="text-xs text-gray-600">Converted</div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
