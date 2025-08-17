import React, { useEffect, useMemo, useState } from "react";
import {
  Box, Grid, Card, CardContent, Typography, Chip, Button, Alert, Tabs, Tab,
  Table, TableHead, TableRow, TableCell, TableBody, TableContainer, Paper,
  Dialog, DialogTitle, DialogContent, DialogActions, TextField, CircularProgress
} from "@mui/material";
import { useTheme } from "@mui/material/styles";
import {
  PlayArrow, Stop, Report, Refresh, Anchor, Shield, PlaylistAddCheck,
  Bolt, Cancel, Timeline, Insights, CheckCircle, Warning,
  AccountBalanceWallet
} from "@mui/icons-material";
import config from "../config";

const RealTrading = () => {
  const theme = useTheme();

  const [activeTab, setActiveTab] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // server data
  const [status, setStatus] = useState(null);          // /status (has "active")
  const [safety, setSafety] = useState(null);          // /safety-status (has stake_usd, caps, etc.)
  const [positions, setPositions] = useState([]);      // /positions
  const [completed, setCompleted] = useState([]);      // /completed-trades
  const [omStatus, setOmStatus] = useState(null);      // /opportunity-manager/status

  // Robust status checking - handle both field names
  const isRunning = Boolean(status?.active ?? status?.is_running);

  // ui state
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [symbolsInput, setSymbolsInput] = useState("BTCUSDT, ETHUSDT");
  const symbols = useMemo(
    () => symbolsInput.split(",").map(s => s.trim().toUpperCase()).filter(Boolean),
    [symbolsInput]
  );

  useEffect(() => {
    const tick = async () => {
      try {
        await Promise.all([
          fetchStatus(), fetchSafety(), fetchPositions(), fetchTrades(), fetchOMStatus()
        ]);
        setError(null);
      } catch (e) {
        setError(e.message || "Fetch failed");
      } finally {
        setLoading(false);
      }
    };
    tick();
    const id = setInterval(tick, 3000);
    return () => clearInterval(id);
  }, []);

  const fetchStatus = async () => {
    const r = await fetch(`${config.API_BASE_URL}${config.ENDPOINTS.REAL_TRADING.STATUS}`);
    const data = await r.json();
    setStatus(data.success ? data.data : data);
  };
  const fetchSafety = async () => {
    const r = await fetch(`${config.API_BASE_URL}${config.ENDPOINTS.REAL_TRADING.SAFETY_STATUS}`);
    const data = await r.json();
    setSafety(data.success ? data.data : data);
  };
  const fetchPositions = async () => {
    const r = await fetch(`${config.API_BASE_URL}${config.ENDPOINTS.REAL_TRADING.POSITIONS}`);
    const j = await r.json();
    setPositions(Array.isArray(j?.data) ? j.data : Array.isArray(j) ? j : []);
  };
  const fetchTrades = async () => {
    const r = await fetch(`${config.API_BASE_URL}${config.ENDPOINTS.REAL_TRADING.COMPLETED_TRADES}?limit=100&backfill=true`);
    const j = await r.json();
    setCompleted(Array.isArray(j?.data) ? j.data : Array.isArray(j) ? j : []);
  };
  const fetchOMStatus = async () => {
    const r = await fetch(`${config.API_BASE_URL}${config.ENDPOINTS.REAL_TRADING.OM_STATUS}`);
    const data = await r.json();
    setOmStatus(data.success ? data.data : data);
  };

  const handleStart = async () => {
    if (!window.confirm("⚠️ WARNING: This will place LIVE orders using $200 per entry. Are your API keys and symbol list correct?")) return;
    if (!window.confirm("🚨 FINAL CHECK: Proceed with REAL MONEY trading now?")) return;
    try {
      const r = await fetch(`${config.API_BASE_URL}${config.ENDPOINTS.REAL_TRADING.START}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbols })
      });
      if (!r.ok) throw new Error(`Start failed (${r.status})`);
      await fetchStatus(); await fetchPositions(); await fetchSafety();
    } catch (e) {
      setError(e.message);
    }
  };

  const handleStop = async () => {
    if (!window.confirm("Stop real trading now?")) return;
    try {
      const r = await fetch(`${config.API_BASE_URL}${config.ENDPOINTS.REAL_TRADING.STOP}`, { method: "POST" });
      if (!r.ok) throw new Error(`Stop failed (${r.status})`);
      await fetchStatus();
    } catch (e) {
      setError(e.message);
    }
  };

  const handleEmergencyStop = async () => {
    if (!window.confirm("🚨 EMERGENCY STOP will immediately halt entries and attempt to flatten all positions. Proceed?")) return;
    try {
      const r = await fetch(`${config.API_BASE_URL}${config.ENDPOINTS.REAL_TRADING.EMERGENCY_STOP}`, { method: "POST" });
      if (!r.ok) throw new Error(`Emergency stop failed (${r.status})`);
      await fetchStatus(); await fetchPositions(); await fetchSafety();
    } catch (e) {
      setError(e.message);
    }
  };

  const closePosition = async (id) => {
    if (!window.confirm("⚠️ Close this live position at market price?")) return;
    try {
      const r = await fetch(`${config.API_BASE_URL}${config.ENDPOINTS.REAL_TRADING.CLOSE_POSITION(id)}`, { method: "POST" });
      if (!r.ok) throw new Error(`Close failed (${r.status})`);
      await fetchPositions(); await fetchTrades();
    } catch (e) {
      setError(e.message);
    }
  };

  const EngineOverview = () => (
    <Grid container spacing={3} sx={{ mb: 3 }}>
      <Grid item xs={12} sm={6} md={2.4}>
        <Card><CardContent>
          <Box display="flex" alignItems="center" mb={1}>
            <Anchor sx={{ mr: 1, color: "primary.main" }} />
            <Typography variant="h6">Engine Status</Typography>
          </Box>
          <Typography variant="h3" color={isRunning ? "success.main" : "grey.500"}>
            {isRunning ? "RUNNING" : "STOPPED"}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Real trading · OM only
          </Typography>
        </CardContent></Card>
      </Grid>

      <Grid item xs={12} sm={6} md={2.4}>
        <Card><CardContent>
          <Box display="flex" alignItems="center" mb={1}>
            <Shield sx={{ mr: 1, color: "info.main" }} />
            <Typography variant="h6">Stake / Risk</Typography>
          </Box>
          <Typography variant="h3">${(safety?.stake_usd ?? 200).toFixed(0)}</Typography>
          <Typography variant="body2" color="text.secondary">
            $7 floor · 0.5% SL · Max daily loss ${Number(safety?.max_daily_loss ?? 0).toFixed(0)}
          </Typography>
        </CardContent></Card>
      </Grid>

      <Grid item xs={12} sm={6} md={2.4}>
        <Card><CardContent>
          <Box display="flex" alignItems="center" mb={1}>
            <PlaylistAddCheck sx={{ mr: 1, color: "secondary.main" }} />
            <Typography variant="h6">Open Positions</Typography>
          </Box>
          <Typography variant="h3">{positions?.length ?? 0}</Typography>
          <Typography variant="body2" color="text.secondary">
            Watching {symbols.length} symbol{symbols.length > 1 ? "s" : ""}
          </Typography>
        </CardContent></Card>
      </Grid>

      <Grid item xs={12} sm={6} md={2.4}>
        <Card><CardContent>
          <Box display="flex" alignItems="center" mb={1}>
            {omStatus?.connected ? <CheckCircle sx={{ mr: 1, color: "success.main" }} /> : <Warning sx={{ mr: 1, color: "warning.main" }} />}
            <Typography variant="h6">OM Status</Typography>
          </Box>
          <Typography variant="h3" color={omStatus?.connected ? "success.main" : "warning.main"}>
            {omStatus?.connected ? "CONNECTED" : "NOT CONNECTED"}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {omStatus?.opportunities_available != null ? `${omStatus.opportunities_available} opportunities` : "—"}
          </Typography>
        </CardContent></Card>
      </Grid>

      {/* 🔹 NEW: Balance */}
      <Grid item xs={12} sm={6} md={2.4}>
        <Card>
          <CardContent>
            <Box display="flex" alignItems="center" mb={1}>
              <AccountBalanceWallet sx={{ mr: 1, color: "success.main" }} />
              <Typography variant="h6">Balance</Typography>
            </Box>
            <Typography variant="h3">
              ${Number(safety?.balance_total_usd ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Available ${Number(safety?.available_usd ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}
            </Typography>
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  );

  const PositionsTable = () => (
    <TableContainer component={Paper} sx={{ mb: 3 }}>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Time</TableCell>
            <TableCell>Symbol</TableCell>
            <TableCell>Side</TableCell>
            <TableCell align="right">Qty</TableCell>
            <TableCell align="right">Entry</TableCell>
            <TableCell align="right">TP</TableCell>
            <TableCell align="right">SL</TableCell>
            <TableCell align="right">P&L</TableCell>
            <TableCell align="right">Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {(positions || []).map((p) => (
            <TableRow key={p.id || p.position_id}>
              <TableCell>{p.entry_time ? new Date(p.entry_time).toLocaleTimeString() : "—"}</TableCell>
              <TableCell><strong>{p.symbol}</strong></TableCell>
              <TableCell>
                <Chip size="small" label={p.side} color={p.side === "LONG" ? "success" : "error"} />
              </TableCell>
              <TableCell align="right">{Number(p.qty ?? p.position_size ?? 0).toFixed(6)}</TableCell>
              <TableCell align="right">${Number(p.entry_price ?? 0).toFixed(4)}</TableCell>
              <TableCell align="right">{p.tp_price ? `$${Number(p.tp_price).toFixed(4)}` : "—"}</TableCell>
              <TableCell align="right">{p.sl_price ? `$${Number(p.sl_price).toFixed(4)}` : "—"}</TableCell>
              <TableCell 
                align="right"
                style={{ 
                  color: Number(p.pnl ?? p.unrealized_pnl ?? 0) >= 0 ? theme.palette.success.main : theme.palette.error.main,
                  fontWeight: 'bold'
                }}
              >
                ${Number(p.pnl ?? p.unrealized_pnl ?? 0).toFixed(2)}
              </TableCell>
              <TableCell align="right">
                <Button size="small" variant="outlined" color="error" startIcon={<Cancel />}
                        onClick={() => closePosition(p.id || p.position_id)}>
                  Close
                </Button>
              </TableCell>
            </TableRow>
          ))}
          {(!positions || positions.length === 0) && (
            <TableRow><TableCell colSpan={9} align="center">No open positions</TableCell></TableRow>
          )}
        </TableBody>
      </Table>
    </TableContainer>
  );

  const TradesTable = () => (
    <TableContainer component={Paper}>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Exit Time</TableCell>
            <TableCell>Symbol</TableCell>
            <TableCell>Side</TableCell>
            <TableCell align="right">Entry</TableCell>
            <TableCell align="right">Exit</TableCell>
            <TableCell align="right">Profit</TableCell>
            <TableCell>Reason</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {(completed || []).slice(0, 20).map((t, i) => (
            <TableRow key={i}>
              <TableCell>{t.exit_time ? new Date(t.exit_time).toLocaleTimeString() : "—"}</TableCell>
              <TableCell><strong>{t.symbol}</strong></TableCell>
              <TableCell>
                <Chip size="small" label={t.side} color={t.side === "LONG" ? "success" : "error"} />
              </TableCell>
              <TableCell align="right">${Number(t.entry_price ?? 0).toFixed(4)}</TableCell>
              <TableCell align="right">${Number(t.exit_price ?? t.close_price ?? 0).toFixed(4)}</TableCell>
              <TableCell
                align="right"
                style={{ 
                  color: Number(t.pnl ?? t.profit ?? 0) >= 0 ? theme.palette.success.main : theme.palette.error.main,
                  fontWeight: 'bold'
                }}
              >
                ${Number(t.pnl ?? t.profit ?? 0).toFixed(2)}
              </TableCell>
              <TableCell>{t.exit_reason || t.reason || "—"}</TableCell>
            </TableRow>
          ))}
          {(!completed || completed.length === 0) && (
            <TableRow><TableCell colSpan={7} align="center">No completed trades</TableCell></TableRow>
          )}
        </TableBody>
      </Table>
    </TableContainer>
  );

  if (loading && !status) {
    return (
      <Box sx={{ height: "60vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom sx={{ mb: 2 }}>
        <Bolt sx={{ mr: 1, verticalAlign: "middle" }} />
        Opportunity Manager — Real Trading
      </Typography>

      <Alert severity="error" sx={{ mb: 2 }}>
        <Typography variant="subtitle1" fontWeight="bold">🚨 REAL MONEY TRADING</Typography>
        This controls live orders using the Opportunity Manager with a fixed ${safety?.stake_usd ?? 200} stake per entry.
        Start narrow (BTCUSDT, ETHUSDT) and confirm leverage/margin mode in Binance Futures.
        <strong> ALL TRADES WILL USE ACTUAL FUNDS!</strong>
      </Alert>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {String(error)}
        </Alert>
      )}

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box display="flex" justifyContent="space-between" alignItems="center">
            <Box>
              <Button variant="outlined" startIcon={<Insights />} sx={{ mr: 1 }} onClick={() => setSettingsOpen(true)}>
                Symbols
              </Button>
              <Button variant="outlined" startIcon={<Refresh />} sx={{ mr: 1 }}
                      onClick={async () => { setLoading(true); await Promise.all([fetchStatus(), fetchSafety(), fetchPositions(), fetchTrades(), fetchOMStatus()]); setLoading(false); }}>
                Refresh
              </Button>
              <Button variant="outlined" color="warning" startIcon={<Report />} sx={{ mr: 1 }} onClick={handleEmergencyStop}>
                Emergency Stop
              </Button>
            </Box>
            <Box>
              {isRunning ? (
                <Button color="error" variant="contained" startIcon={<Stop />} onClick={handleStop}>
                  Stop Real Trading
                </Button>
              ) : (
                <Button color="success" variant="contained" startIcon={<PlayArrow />} onClick={handleStart}>
                  Start Real Trading
                </Button>
              )}
            </Box>
          </Box>
        </CardContent>
      </Card>

      <EngineOverview />

      {/* Safety Status Card */}
      {safety && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom display="flex" alignItems="center" gap={1}>
              <Shield color="warning" />
              Safety Status & Limits
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={6} sm={3}>
                <Typography variant="body2" color="text.secondary">Daily P&L</Typography>
                <Typography variant="h6" color={safety.daily_pnl >= 0 ? "success.main" : "error.main"}>
                  ${Number(safety.daily_pnl ?? 0).toFixed(2)}
                </Typography>
              </Grid>
              <Grid item xs={6} sm={3}>
                <Typography variant="body2" color="text.secondary">Total P&L</Typography>
                <Typography variant="h6" color={safety.total_pnl >= 0 ? "success.main" : "error.main"}>
                  ${Number(safety.total_pnl ?? 0).toFixed(2)}
                </Typography>
              </Grid>
              <Grid item xs={6} sm={3}>
                <Typography variant="body2" color="text.secondary">Emergency Stop</Typography>
                <Chip 
                  label={safety.emergency_stop ? "ACTIVE" : "NORMAL"} 
                  color={safety.emergency_stop ? "error" : "success"}
                  size="small"
                />
              </Grid>
              <Grid item xs={6} sm={3}>
                <Typography variant="body2" color="text.secondary">Pure 3-Rule Mode</Typography>
                <Chip 
                  label={safety.pure_3_rule_mode ? "ENABLED" : "DISABLED"} 
                  color={safety.pure_3_rule_mode ? "primary" : "default"}
                  size="small"
                />
              </Grid>
            </Grid>
          </CardContent>
        </Card>
      )}

      <Box sx={{ borderBottom: 1, borderColor: "divider", mb: 2 }}>
        <Tabs value={activeTab} onChange={(e, v) => setActiveTab(v)}>
          <Tab label="Positions" icon={<Timeline />} />
          <Tab label="Completed Trades" icon={<PlaylistAddCheck />} />
        </Tabs>
      </Box>

      {activeTab === 0 && <PositionsTable />}
      {activeTab === 1 && <TradesTable />}

      <Dialog open={settingsOpen} onClose={() => setSettingsOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Trading Symbols Configuration</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            <strong>Warning:</strong> Only add symbols you understand and have verified on Binance Futures.
            Start with major pairs like BTCUSDT, ETHUSDT.
          </Alert>
          <TextField 
            fullWidth 
            label="Comma-separated symbols" 
            helperText="Example: BTCUSDT, ETHUSDT, BNBUSDT"
            value={symbolsInput} 
            onChange={(e) => setSymbolsInput(e.target.value)}
            sx={{ mt: 2 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSettingsOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={() => setSettingsOpen(false)}>Save</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default RealTrading;
