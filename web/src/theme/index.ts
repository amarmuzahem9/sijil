import { createTheme } from '@mui/material/styles';

export const theme = createTheme({
  direction: 'rtl',
  palette: {
    primary: { main: '#0f5fa8' },
    secondary: { main: '#00897b' },
    background: { default: '#f4f6f9' },
  },
  typography: {
    fontFamily: '"Cairo", "Segoe UI", Tahoma, sans-serif',
    button: { fontWeight: 600, textTransform: 'none' },
  },
  shape: { borderRadius: 10 },
});
