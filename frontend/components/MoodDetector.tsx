
import React, { useRef, useState } from 'react';
import { buildApiUrl } from '../constants';

interface MoodDetectorProps {
  onMoodDetected: (mood: string, suggestedMovies?: string[]) => void;
}

const SUPPORTED_MOODS = ['HAPPY', 'SAD', 'BORED', 'EXCITED', 'CALM', 'MOTIVATED'];

const MoodDetector: React.FC<MoodDetectorProps> = ({ onMoodDetected }) => {
  const [isActive, setIsActive] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [detectedMood, setDetectedMood] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [countdown, setCountdown] = useState(3);
  
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  const startSensors = async () => {
    setError(null);
    setIsActive(true);
    setDetectedMood(null);
    setIsRecording(false);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ 
        video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' },
        audio: true
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
    } catch (err: any) {
      console.warn("Sensor access denied:", err);
      setError("Camera and Microphone are required for AI prediction. Please enable permissions.");
    }
  };

  const stopDetector = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    setIsActive(false);
    setIsRecording(false);
  };

  const startScan = () => {
    if (!streamRef.current) return;
    setIsRecording(true);
    setCountdown(3);
    audioChunksRef.current = [];

    const audioStream = new MediaStream(streamRef.current.getAudioTracks());
    const mediaRecorder = new MediaRecorder(audioStream);
    mediaRecorderRef.current = mediaRecorder;

    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        audioChunksRef.current.push(event.data);
      }
    };

    mediaRecorder.onstop = async () => {
      processMultimodalData();
    };

    mediaRecorder.start();

    const interval = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          mediaRecorder.stop();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  };

  const processMultimodalData = async () => {
    if (!videoRef.current || !canvasRef.current) return;

    setIsAnalyzing(true);
    setIsRecording(false);

    try {
      const canvas = canvasRef.current;
      const video = videoRef.current;
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext('2d');
      if (!ctx) throw new Error('Canvas context failed');

      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

      const frameBlob: Blob = await new Promise((resolve, reject) => {
        canvas.toBlob((blob) => {
          if (blob) {
            resolve(blob);
          } else {
            reject(new Error('Failed to capture video frame'));
          }
        }, 'image/jpeg', 0.8);
      });

      const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
      const formData = new FormData();
      formData.append('video_frame', frameBlob, 'frame.jpg');
      formData.append('audio_sample', audioBlob, 'audio.webm');

      const res = await fetch(buildApiUrl('/live_predict'), {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        throw new Error(`Backend request failed with status ${res.status}`);
      }

      const data = await res.json();
      const mood = (data.mood || 'CALM').toUpperCase();
      const finalMood = SUPPORTED_MOODS.includes(mood) ? mood : 'CALM';
      const suggestedMovies: string[] = Array.isArray(data.movies)
        ? data.movies.map((movie: any) => movie?.title).filter(Boolean)
        : [];

      setDetectedMood(finalMood);
      onMoodDetected(finalMood, suggestedMovies);

      setTimeout(() => {
        stopDetector();
        setIsAnalyzing(false);
      }, 3000);
    } catch (err) {
      console.error('Multimodal Analysis failed:', err);
      setError('Backend not running or unable to process input.');
      setIsAnalyzing(false);
    }
  };

  return (
    <div className="relative z-[110]">
      {!isActive ? (
        <button 
          onClick={startSensors}
          className="flex items-center space-x-2 bg-gradient-to-r from-netflix-red to-red-800 text-white px-6 py-3 rounded-full font-bold shadow-2xl hover:scale-105 transition-all group ring-1 ring-white/20"
        >
          <i className="fas fa-face-smile-beam group-hover:rotate-12 transition-transform"></i>
          <span>AI Mood Scan</span>
        </button>
      ) : (
        <div className="fixed inset-0 bg-black/98 backdrop-blur-2xl flex items-center justify-center p-4 z-[120]">
          <div className="bg-[#111] w-full max-w-lg rounded-2xl overflow-hidden shadow-[0_0_80px_rgba(229,9,20,0.4)] border border-white/5 animate-zoom-in">
            <div className="p-5 border-b border-white/5 flex justify-between items-center">
              <div className="flex items-center space-x-3">
                <div className="flex space-x-1">
                  <div className="w-1.5 h-1.5 bg-red-500 rounded-full animate-pulse"></div>
                  <div className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-pulse delay-75"></div>
                  <div className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse delay-150"></div>
                </div>
                <h3 className="font-black text-white uppercase tracking-[0.2em] text-xs">Biometric Mood Predictor</h3>
              </div>
              <button onClick={stopDetector} className="text-gray-500 hover:text-white transition-colors p-2">
                <i className="fas fa-times text-xl"></i>
              </button>
            </div>
            
            <div className="relative aspect-video bg-black overflow-hidden">
              <video ref={videoRef} autoPlay muted playsInline className={`w-full h-full object-cover mirror transition-all duration-700 ${detectedMood ? 'opacity-20 blur-xl scale-125' : 'opacity-100'}`} />
              <canvas ref={canvasRef} className="hidden" />
              
              {/* Scan Overlay UI */}
              {!detectedMood && !isAnalyzing && (
                 <div className="absolute inset-0 pointer-events-none">
                    <div className="absolute top-4 left-4 border-l-2 border-t-2 border-white/30 w-8 h-8"></div>
                    <div className="absolute top-4 right-4 border-r-2 border-t-2 border-white/30 w-8 h-8"></div>
                    <div className="absolute bottom-4 left-4 border-l-2 border-b-2 border-white/30 w-8 h-8"></div>
                    <div className="absolute bottom-4 right-4 border-r-2 border-b-2 border-white/30 w-8 h-8"></div>
                    
                    {isRecording && (
                      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 flex flex-col items-center">
                        <div className="text-7xl font-black text-white mb-4 animate-ping opacity-50">{countdown}</div>
                        <div className="flex items-end space-x-1 h-12">
                           {[1,2,3,4,5,6,7,8].map(i => (
                             <div key={i} className="w-1 bg-netflix-red rounded-full animate-waveform" style={{ animationDelay: `${i * 0.1}s` }}></div>
                           ))}
                        </div>
                        <p className="mt-4 text-xs font-bold text-netflix-red tracking-widest animate-pulse uppercase">Recording & Capturing...</p>
                      </div>
                    )}
                 </div>
              )}

              {isAnalyzing && (
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/60 backdrop-blur-md z-30">
                  <div className="relative">
                    <div className="w-24 h-24 border-2 border-white/5 rounded-full"></div>
                    <div className="absolute inset-0 w-24 h-24 border-t-2 border-netflix-red rounded-full animate-spin"></div>
                    <div className="absolute inset-4 w-16 h-16 border-b-2 border-blue-500 rounded-full animate-spin-slow"></div>
                  </div>
                  <p className="mt-8 font-black tracking-[0.4em] text-white animate-pulse text-[10px] uppercase">Cross-Referencing modalities...</p>
                </div>
              )}

              {detectedMood && (
                <div className="absolute inset-0 flex flex-col items-center justify-center z-40 animate-fade-in">
                  <div className="text-9xl mb-6 drop-shadow-[0_0_30px_rgba(255,255,255,0.2)] animate-bounce-gentle">
                    {detectedMood === 'HAPPY' && '😊'}
                    {detectedMood === 'SAD' && '😢'}
                    {detectedMood === 'BORED' && '😐'}
                    {detectedMood === 'EXCITED' && '🤩'}
                    {detectedMood === 'CALM' && '😌'}
                    {detectedMood === 'MOTIVATED' && '💪'}
                  </div>
                  <div className="text-center px-4">
                    <h2 className="text-5xl font-black text-white tracking-tighter uppercase italic">{detectedMood}!</h2>
                    <div className="h-0.5 w-full bg-gradient-to-r from-transparent via-netflix-red to-transparent mt-4"></div>
                    <p className="mt-4 text-gray-400 text-[10px] font-bold uppercase tracking-[0.2em]">Predicted by Multimodal Neural Engine</p>
                  </div>
                </div>
              )}
            </div>

            <div className="p-8 bg-[#141414]">
              {!detectedMood && !isAnalyzing && !isRecording && (
                <div className="space-y-6">
                  <div className="text-center">
                    <p className="text-gray-300 text-sm font-medium">To provide the most accurate recommendation, the AI will analyze your facial cues and voice pattern.</p>
                  </div>
                  <button 
                    onClick={startScan}
                    className="w-full bg-white text-black font-black py-4 rounded-xl shadow-[0_15px_30px_rgba(255,255,255,0.1)] hover:bg-gray-200 active:scale-95 transition-all uppercase tracking-widest flex items-center justify-center space-x-3"
                  >
                    <i className="fas fa-play"></i>
                    <span>Start Neural Scan</span>
                  </button>
                </div>
              )}

              {error && (
                <div className="p-4 bg-red-900/20 border border-red-500/30 rounded-lg">
                   <p className="text-red-500 text-xs font-bold text-center leading-relaxed italic">{error}</p>
                   <button onClick={startSensors} className="mt-2 w-full text-[10px] text-gray-400 underline uppercase font-bold hover:text-white">Retry Permissions</button>
                </div>
              )}

              <div className="mt-8 flex items-center justify-center space-x-6 opacity-30">
                 <div className="flex items-center space-x-1">
                    <i className="fas fa-video text-[10px]"></i>
                    <span className="text-[8px] font-bold uppercase">Vision</span>
                 </div>
                 <div className="flex items-center space-x-1">
                    <i className="fas fa-microphone text-[10px]"></i>
                    <span className="text-[8px] font-bold uppercase">Audio</span>
                 </div>
                 <div className="flex items-center space-x-1 text-netflix-red">
                    <i className="fas fa-brain text-[10px]"></i>
                    <span className="text-[8px] font-bold uppercase">Inference</span>
                 </div>
              </div>
            </div>
          </div>
        </div>
      )}
      <style>{`
        .mirror { transform: scaleX(-1); }
        .animate-spin-slow { animation: spin 3s linear infinite; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @keyframes waveform {
          0%, 100% { height: 10px; }
          50% { height: 40px; }
        }
        .animate-waveform { animation: waveform 0.6s ease-in-out infinite; }
        @keyframes bounce-gentle {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-15px); }
        }
        .animate-bounce-gentle { animation: bounce-gentle 2s ease-in-out infinite; }
      `}</style>
    </div>
  );
};

export default MoodDetector;
