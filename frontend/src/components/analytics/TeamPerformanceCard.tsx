import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { 
  Users, 
  Phone, 
  TrendingUp, 
  Target,
  Award,
  Activity
} from 'lucide-react'
import type { TeamPerformanceResponse } from '@/hooks/use-analytics-query'

interface TeamPerformanceCardProps {
  performance?: TeamPerformanceResponse
  isLoading: boolean
}

export default function TeamPerformanceCard({ performance, isLoading }: TeamPerformanceCardProps) {
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Team Performance</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-4 bg-gray-200 rounded animate-pulse" />
            ))}
          </div>
        </CardContent>
      </Card>
    )
  }

  if (!performance) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Team Performance</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-gray-500">No performance data available</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center">
              <Users className="w-4 h-4 mr-2" />
              Team Size
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{performance.team_size}</div>
            <p className="text-xs text-gray-500">Active members</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center">
              <Phone className="w-4 h-4 mr-2" />
              Total Calls
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{performance.reports.total_calls.toLocaleString()}</div>
            <p className="text-xs text-gray-500">{performance.reports.pickup_rate}% pickup rate</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center">
              <Award className="w-4 h-4 mr-2" />
              Total Points
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{performance.scores.total_points}</div>
            <p className="text-xs text-gray-500">{performance.scores.days_with_reports} days with reports</p>
          </CardContent>
        </Card>
      </div>

      {/* Detailed Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Reports Metrics */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center">
              <Activity className="w-5 h-5 mr-2" />
              Reports & Calls
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">Total Reports</span>
                <Badge variant="outline">{performance.reports.total_reports}</Badge>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">Calls Picked</span>
                <span className="font-semibold">{performance.reports.calls_picked.toLocaleString()}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">Enrollments</span>
                <span className="font-semibold">{performance.reports.enrollments}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">Payments</span>
                <span className="font-semibold">{performance.reports.payments}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">Avg Daily Calls</span>
                <span className="font-semibold">{performance.reports.avg_daily_calls}</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Leads Metrics */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center">
              <Target className="w-5 h-5 mr-2" />
              Lead Performance
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">Total Leads</span>
                <Badge variant="outline">{performance.leads.total_leads}</Badge>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">Converted Leads</span>
                <span className="font-semibold">{performance.leads.converted_leads}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">Paid Leads</span>
                <span className="font-semibold">{performance.leads.paid_leads}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">Conversion Rate</span>
                <Badge 
                  variant={performance.leads.conversion_rate >= 20 ? "default" : "outline"}
                >
                  {performance.leads.conversion_rate}%
                </Badge>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">Payment Rate</span>
                <Badge 
                  variant={performance.leads.payment_rate >= 50 ? "default" : "outline"}
                >
                  {performance.leads.payment_rate}%
                </Badge>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Performance Indicators */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center">
            <TrendingUp className="w-5 h-5 mr-2" />
            Performance Indicators
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">
                {performance.scores.avg_daily_points.toFixed(1)}
              </div>
              <div className="text-xs text-gray-600">Avg Daily Points</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">
                {performance.reports.pickup_rate.toFixed(1)}%
              </div>
              <div className="text-xs text-gray-600">Call Pickup Rate</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-purple-600">
                {performance.leads.conversion_rate.toFixed(1)}%
              </div>
              <div className="text-xs text-gray-600">Conversion Rate</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-orange-600">
                {performance.leads.payment_rate.toFixed(1)}%
              </div>
              <div className="text-xs text-gray-600">Payment Rate</div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
