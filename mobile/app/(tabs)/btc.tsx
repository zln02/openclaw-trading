import { SafeAreaView, ScrollView, Text, View } from 'react-native';
import { PriceCard } from '../../components/PriceCard';
import { SignalBadge } from '../../components/SignalBadge';
import { MiniChart } from '../../components/MiniChart';
import { TradeList } from '../../components/TradeList';
import { AllocationStrip } from '../../components/AllocationStrip';
import { useSignals } from '../../hooks/useSignals';
import { useAllocationOverview, useRegimeOverview } from '../../hooks/useOverview';
import { useWebSocket } from '../../hooks/useWebSocket';

export default function BtcScreen() {
  const { data } = useSignals('btc');
  const { data: allocation } = useAllocationOverview();
  const { data: regime } = useRegimeOverview();
  const { events } = useWebSocket();
  const score = Number(data?.composite_score || 0);
  const trend = String(data?.trend || 'SIDEWAYS');

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: '#f3efe4' }}>
      <ScrollView contentContainerStyle={{ padding: 18, gap: 14 }}>
        <PriceCard title="BTC Signal" value={`${score.toFixed(0)} pt`} subtitle={`Regime ${data?.regime || 'TRANSITION'}`} accent="#112b1f" />
        <View style={{ flexDirection: 'row', gap: 10 }}>
          <SignalBadge label={`Trend ${trend}`} tone={trend === 'UPTREND' ? 'good' : trend === 'DOWNTREND' ? 'bad' : 'neutral'} />
          <SignalBadge label={`F&G ${Number(data?.fg_index || 50).toFixed(0)}`} tone="neutral" />
          <SignalBadge label={`Regime ${regime?.current_regime || data?.regime || 'TRANSITION'}`} tone="neutral" />
        </View>
        <MiniChart values={[42, 55, 51, 63, 67, 61, score || 58]} color="#112b1f" />
        <AllocationStrip
          btc={Number(allocation?.btc_pct || 0)}
          kr={Number(allocation?.kr_pct || 0)}
          us={Number(allocation?.us_pct || 0)}
          cash={Number(allocation?.cash_pct || 0)}
        />
        <View style={{ backgroundColor: '#fffaf0', borderRadius: 22, padding: 18 }}>
          <Text style={{ fontSize: 18, fontWeight: '700', color: '#112b1f' }}>Recommendation</Text>
          <Text style={{ marginTop: 8, color: '#4d5c51' }}>{data?.recommendation || 'HOLD'}</Text>
          <Text style={{ marginTop: 8, color: '#6a756d' }}>
            Regime confidence {Number(regime?.confidence || 0).toFixed(2)}
          </Text>
        </View>
        <TradeList
          title="Recent Stream"
          items={events.slice(0, 5).map((item) => `${item.type || 'event'} · ${item.timestamp || '-'}`)}
        />
      </ScrollView>
    </SafeAreaView>
  );
}
