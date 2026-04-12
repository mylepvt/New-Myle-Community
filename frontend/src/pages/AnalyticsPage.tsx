import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { 
  BarChart3, 
  TrendingUp, 
  Users, 
  Phone, 
  Target,
  Award,
  Activity,
  Calendar,
  Download
} from 'lucide-react'
import { 
  useTeamPerformanceQuery,
  useIndividualPerformanceQuery,
  useLeaderboardQuery,
  useSystemOverviewQuery,
  useDailyTrendsQuery
} from '@/hooks/use-analytics-query'
import { useAuthMeQuery } from '@/hooks/use-auth-me-query'
import TeamPerformanceCard from '@/components/analytics/TeamPerformanceCard'
import IndividualPerformanceCard from '@/components/analytics/IndividualPerformanceCard'
import LeaderboardTable from '@/components/analytics/LeaderboardTable'
import SystemOverviewCard from '@/components/analytics/SystemOverviewCard'
import DailyTrendsChart from '@/components/analytics/DailyTrendsChart'

export default function AnalyticsPage() {
  const [selectedDays, setSelectedDays] = useState(30)
  const [activeTab, setActiveTab] = useState('overview')
  const { data: authData } = useAuthMeQuery()
  
  const teamPerformance = useTeamPerformanceQuery(selectedDays)
  const individualPerformance = useIndividualPerformanceQuery(undefined, selectedDays)
  const leaderboard = useLeaderboardQuery(selectedDays)
  const systemOverview = useSystemOverviewQuery(selectedDays)
  const dailyTrends = useDailyTrendsQuery(undefined, selectedDays)

  const isAdmin = authData?.role === 'admin'
  const isLeader = authData?.role === 'leader'
  const canViewTeam = isAdmin || isLeader

  return (
    <div className="container mx-auto p-6">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold mb-2">Analytics & Reports</h1>
            <p className="text-gray-600">
              Performance metrics and insights for your team
            </p>
          </div>
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2">
              <Calendar className="w-4 h-4" />
              <select
                value={selectedDays}
                onChange={(e) => setSelectedDays(Number(e.target.value))}
                className="px-3 py-2 border rounded-md text-sm"
              >
                <option value={7}>7 days</option>
                <option value={30}>30 days</option>
                <option value={90}>90 days</option>
              </select>
            </div>
            <Badge variant="outline" className="text-sm">
              {authData?.role?.toUpperCase()}
            </Badge>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          {canViewTeam && <TabsTrigger value="team">Team</TabsTrigger>}
          <TabsTrigger value="leaderboard">Leaderboard</TabsTrigger>
          {isAdmin && <TabsTrigger value="system">System</TabsTrigger>}
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {/* Individual Performance */}
            <IndividualPerformanceCard 
              performance={individualPerformance.data}
              isLoading={individualPerformance.isLoading}
            />

            {/* Daily Trends */}
            <DailyTrendsChart 
              trends={dailyTrends.data?.trends}
              isLoading={dailyTrends.isLoading}
            />

            {/* Quick Stats */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center">
                  <Activity className="w-5 h-5 mr-2" />
                  Quick Stats
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Reports Submitted</span>
                    <span className="font-semibold">
                      {individualPerformance.data?.reports.total_reports || 0}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Total Calls</span>
                    <span className="font-semibold">
                      {individualPerformance.data?.reports.total_calls || 0}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Enrollments</span>
                    <span className="font-semibold">
                      {individualPerformance.data?.reports.total_enrollments || 0}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Points Earned</span>
                    <span className="font-semibold">
                      {individualPerformance.data?.scores.total_points || 0}
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Team Performance Tab */}
        {canViewTeam && (
          <TabsContent value="team" className="space-y-6">
            <TeamPerformanceCard 
              performance={teamPerformance.data}
              isLoading={teamPerformance.isLoading}
            />
          </TabsContent>
        )}

        {/* Leaderboard Tab */}
        <TabsContent value="leaderboard" className="space-y-6">
          <LeaderboardTable 
              leaderboard={leaderboard.data}
              isLoading={leaderboard.isLoading}
            />
        </TabsContent>

        {/* System Overview Tab */}
        {isAdmin && (
          <TabsContent value="system" className="space-y-6">
            <SystemOverviewCard 
              overview={systemOverview.data}
              isLoading={systemOverview.isLoading}
            />
          </TabsContent>
        )}
      </Tabs>

      {/* Export Options */}
      <div className="mt-8 p-4 bg-gray-50 rounded-lg">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-medium">Export Data</h3>
            <p className="text-sm text-gray-600">Download analytics data for offline analysis</p>
          </div>
          <div className="flex space-x-2">
            <Button variant="outline" size="sm">
              <Download className="w-4 h-4 mr-2" />
              Export CSV
            </Button>
            <Button variant="outline" size="sm">
              <Download className="w-4 h-4 mr-2" />
              Export Excel
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
