import { EmojiButton } from 'https://cdn.jsdelivr.net/npm/@joeattardi/emoji-button@4.6.2/dist/index.js';

const bodyElem = document.body;
const username = bodyElem.dataset.username;
const friend = bodyElem.dataset.friend;
const friendAvatarUrl = bodyElem.dataset.friendAvatarUrl;

window.socket = io({
  auth: { username }
});

const messagesList = document.getElementById('messages');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const typingDiv = document.getElementById('typing');
const emojiBtn = document.getElementById('emojiBtn');
const picker = new EmojiButton({
  position: 'top-end',
  zIndex: 9999
});
const uploadBtn = document.getElementById('uploadBtn');
const fileInput = document.getElementById('fileInput');

const voiceCallBtn = document.getElementById('voiceCallBtn');
const videoCallBtn = document.getElementById('videoCallBtn');
const endCallBtn = document.getElementById('endCallBtn');
const videoCallDiv = document.getElementById('video-call');
const localVideo = document.getElementById('localVideo');
const remoteVideo = document.getElementById('remoteVideo');
const incomingCallModal = document.getElementById('incomingCallModal');

const acceptCallBtn = document.getElementById('acceptCallBtn');
const rejectCallBtn = document.getElementById('rejectCallBtn');

const recordBtn = document.getElementById('recordBtn');

let localStream = null;
let peerConnection = null;
let isVideoCall = false;

let mediaRecorder;
let audioChunks = [];
let isRecording = false;

const configuration = {
  iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
};

// Emoji picker setup
picker.on('emoji', emoji => {
  let emojiStr = typeof emoji === 'string' ? emoji : (emoji.emoji || '');
  messageInput.value += emojiStr;
  messageInput.focus();
});
emojiBtn.addEventListener('click', () => picker.togglePicker(emojiBtn));

// File upload handlers
uploadBtn.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', async () => {
  const file = fileInput.files[0];
  if (!file) return;
  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch('/upload', { method: 'POST', body: formData });
    const data = await res.json();
    if (data.file_url) {
      console.log("Yüklenen dosya URL'si:", data.file_url);
      // Only emit the uploaded file URL here, and nowhere else
      socket.emit('message', { text: data.file_url, friend });
      messageInput.value = '';
    } else {
      alert("Dosya yüklenemedi.");
    }
  } catch (err) {
    alert("Yükleme sırasında hata oluştu.");
  }
  fileInput.value = '';
});

// Sesli mesaj kaydı butonu
recordBtn.addEventListener('click', async () => {
  if (isRecording) {
    mediaRecorder.stop();
    recordBtn.textContent = '🎤';
    isRecording = false;
  } else {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      alert('Tarayıcınız ses kaydını desteklemiyor.');
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder = new MediaRecorder(stream);
      audioChunks = [];

      mediaRecorder.ondataavailable = e => {
        audioChunks.push(e.data);
      };

     mediaRecorder.onstop = async () => {
       const audioBlob = new Blob(audioChunks, { type: 'audio/webm;codecs=opus' });
       const formData = new FormData();
       const timestamp = Date.now();
       const uniqueFilename = `voice_message_${timestamp}.webm`;
       formData.append('file', audioBlob, uniqueFilename);

       // Mikrofonu kapat (stream'deki tüm trackleri durdur)
       if (mediaRecorder.stream) {
         mediaRecorder.stream.getTracks().forEach(track => track.stop());
       }

       try {
         const res = await fetch('/upload', { method: 'POST', body: formData });
         const data = await res.json();
         if (data.file_url) {
           console.log("Ses dosyası gönderiliyor:", data.file_url);
           socket.emit('message', { text: data.file_url, friend });
         } else {
           alert('Ses mesajı yüklenemedi.');
         }
       } catch (error) {
         alert('Ses mesajı yüklenirken hata oluştu.');
         console.error(error);
       }
     };

      mediaRecorder.start();
      recordBtn.textContent = '■';  // Kayıt durdurma işareti
      isRecording = true;
    } catch (error) {
      alert('Mikrofon erişimi reddedildi.');
      console.error(error);
    }
  }
});

// Send message
sendBtn.addEventListener('click', () => {
  const text = messageInput.value.trim();
  if (!text) return;
  socket.emit('message', { text: text, friend: friend });
  messageInput.value = '';
});
messageInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendBtn.click();
  } else {
    socket.emit('typing', { friend });
  }
});

// Yardımcı fonksiyon: Süreyi dakika:saniye formatında yapar
function formatDuration(seconds) {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

// Render messages
let messages = [];
window.renderMessages = function(messages) {
  messagesList.innerHTML = '';

  messages.forEach(msg => {
    const li = document.createElement('li');
    li.classList.add('message-container', msg.sender_name === username ? 'outgoing' : 'incoming');

    if (msg.sender_name !== username) {
      const avatar = document.createElement('img');
      avatar.src = friendAvatarUrl;
      avatar.alt = msg.sender_name;
      avatar.classList.add('avatar');
      li.appendChild(avatar);
    }

    const bubble = document.createElement('div');
    bubble.classList.add('message', msg.sender_name === username ? 'outgoing' : 'incoming');

    if (msg.sender_name !== username) {
      const who = document.createElement('div');
      who.classList.add('sender-name');
      who.textContent = msg.sender_name;
      bubble.appendChild(who);
    }

    const textDiv = document.createElement('div');
    textDiv.classList.add('text');

    if (msg.message.match(/\.(mp3|wav|ogg|webm)$/i)) {
  // Sesli mesaj için kapsayıcı div
  const audioWrapper = document.createElement('div');
  Object.assign(audioWrapper.style, {
    display: 'flex',
    alignItems: 'center',
    background: '#f1f0f0',
    borderRadius: '16px',
    padding: '8px 12px',
    maxWidth: '260px',
    minWidth: '180px',
    boxShadow: '0 1px 2px rgba(0,0,0,0.1)',
    marginTop: '5px',
    gap: '10px'
  });

  // Audio elementi oluştur
  const audio = document.createElement('audio');
  audio.controls = true;

  let audioSrc = msg.message;

  // Eğer url içinde iki kez /static/uploads/ varsa, tekrar eden kısmı kaldır
  const duplicatePath = '/static/uploads/';
  const firstIndex = audioSrc.indexOf(duplicatePath);
  const lastIndex = audioSrc.lastIndexOf(duplicatePath);
  if (firstIndex !== -1 && lastIndex !== -1 && firstIndex !== lastIndex) {
    audioSrc = audioSrc.substring(lastIndex);
  }

  // Eğer url protokol içermezse (http/https) tam URL oluştur
  if (!audioSrc.startsWith('http')) {
    audioSrc = window.location.origin + audioSrc;
  }

  audio.src = audioSrc;

  // Stil ayarları
  Object.assign(audio.style, {
    flex: '1',
    outline: 'none',
    borderRadius: '8px',
    backgroundColor: '#fff'
  });

  audioWrapper.appendChild(audio);
  textDiv.appendChild(audioWrapper);
} else if (msg.message.match(/\.(jpg|jpeg|png|gif)$/i)) {
      const img = document.createElement('img');
      img.src = msg.message;
      img.alt = "Gönderilen resim";
      img.style.maxWidth = '200px';
      img.style.borderRadius = '8px';
      textDiv.appendChild(img);
    } else if (msg.message.match(/^\/static\/uploads\//)) {
      const link = document.createElement('a');
      link.href = msg.message;
      link.target = '_blank';
      link.textContent = "Dosyayı Görüntüle";
      textDiv.appendChild(link);
    } else {
      textDiv.textContent = msg.message;
    }

    bubble.appendChild(textDiv);

    const timeDiv = document.createElement('div');
    timeDiv.classList.add('time');
    const date = new Date(msg.time);
    timeDiv.textContent = `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;

    if (msg.sender_name === username) {
      const readSpan = document.createElement('span');
      readSpan.classList.add('read-receipt');
      readSpan.textContent = msg.read ? '✓✓' : '✓';
      if (msg.read) readSpan.classList.add('read');
      timeDiv.appendChild(readSpan);
    }

    bubble.appendChild(timeDiv);

    li.appendChild(bubble);
    messagesList.appendChild(li);
  });

  messagesList.scrollTop = messagesList.scrollHeight;
};

// Load message history
async function loadMessageHistory() {
  try {
    const resp = await fetch(`/messages?friend=${encodeURIComponent(friend)}`);
    if (!resp.ok) throw new Error("Sunucudan mesajlar alınamadı");
    const data = await resp.json();
    if (data?.messages) {
      messages = data.messages.map(m => ({
        sender_name: m.sender_name,
        message: m.message,
        time: m.timestamp,
        read: m.okundu,
        avatar_url: m.sender_avatar || ''
      }));
      renderMessages(messages);
    }
  } catch (err) {
    console.error("Mesaj geçmişi yüklenirken hata:", err);
  }
}

// Socket.io event handlers
socket.on('connect', () => {
  socket.emit('join', { friend });
  loadMessageHistory();
});

socket.on('message', msg => {
  if (msg.user === friend || msg.user === username) {
    messages.push({
      sender_name: msg.user,
      message: msg.text,
      time: msg.timestamp,
      read: false,
      avatar_url: ''
    });
    renderMessages(messages);
    if (msg.user === friend) {
      socket.emit('messages_read', { friend });
    }
  }
});

socket.on('display_typing', data => {
  if (data.from === friend) {
    typingDiv.style.display = 'inline';
    typingDiv.textContent = `${friend} yazıyor...`;
    clearTimeout(typingDiv._timeout);
    typingDiv._timeout = setTimeout(() => {
      typingDiv.style.display = 'none';
    }, 1500);
  }
});

socket.on('messages_read', data => {
  if (data.reader === friend) {
    messages = messages.map(m => (m.sender_name === username ? { ...m, read: true } : m));
    renderMessages(messages);
  }
});

// --- Call functions ---

let pendingCandidates = [];

async function addPendingCandidates() {
  if (pendingCandidates.length && peerConnection) {
    for (const candidate of pendingCandidates) {
      try {
        await peerConnection.addIceCandidate(new RTCIceCandidate(candidate));
      } catch (e) {
        console.error('Pending ICE candidate eklenirken hata:', e);
      }
    }
    pendingCandidates = [];
  }
}

window.startCall = async function(video) {
  isVideoCall = video;
  try {
    localStream = await navigator.mediaDevices.getUserMedia({ video, audio: true });
    localVideo.srcObject = localStream;
    videoCallDiv.style.display = 'block';

    peerConnection = new RTCPeerConnection(configuration);
    localStream.getTracks().forEach(track => peerConnection.addTrack(track, localStream));

    peerConnection.onicecandidate = event => {
      if (event.candidate) {
        socket.emit('ice_candidate', { candidate: event.candidate, friend });
      }
    };

    peerConnection.ontrack = event => {
      remoteVideo.srcObject = event.streams[0];
    };

    await addPendingCandidates();

    const offer = await peerConnection.createOffer();
    await peerConnection.setLocalDescription(offer);

    const callType = isVideoCall ? 'video' : 'voice';
    socket.emit('call_offer', { friend, offer, call_type: callType });

    hideIncomingCallModal();
  } catch (err) {
    alert('Kameraya ve mikrofona erişim reddedildi veya arama başlatılamadı.');
    console.error(err);
  }
}

function endCall(emit = true) {
  if (peerConnection) {
    peerConnection.close();
    peerConnection = null;
  }
  if (localStream) {
    localStream.getTracks().forEach(track => track.stop());
    localStream = null;
  }
  videoCallDiv.style.display = 'none';
  localVideo.srcObject = null;
  remoteVideo.srcObject = null;
  hideIncomingCallModal();

  if (emit) {
    socket.emit('call_end', { friend });
  }
}

function showIncomingCallModal(caller, video) {
  incomingCallModal.style.display = 'block';
  incomingCallModal.querySelector('p strong').textContent = caller;
  incomingCallModal.dataset.video = video;
}

function hideIncomingCallModal() {
  incomingCallModal.style.display = 'none';
  incomingCallModal.dataset.video = '';
  incomingCallModal.dataset.offer = '';
}

// Gelen aramayı kabul et
acceptCallBtn.onclick = async () => {
  try {
    const video = incomingCallModal.dataset.video === 'true';
    localStream = await navigator.mediaDevices.getUserMedia({ video, audio: true });
    localVideo.srcObject = localStream;
    videoCallDiv.style.display = 'block';

    peerConnection = new RTCPeerConnection(configuration);
    localStream.getTracks().forEach(track => peerConnection.addTrack(track, localStream));

    peerConnection.onicecandidate = event => {
      if (event.candidate) {
        socket.emit('ice_candidate', { candidate: event.candidate, friend });
      }
    };

    peerConnection.ontrack = event => {
      remoteVideo.srcObject = event.streams[0];
    };

    await addPendingCandidates();

    await peerConnection.setRemoteDescription(new RTCSessionDescription(JSON.parse(incomingCallModal.dataset.offer)));
    const answer = await peerConnection.createAnswer();
    await peerConnection.setLocalDescription(answer);

    socket.emit('call_answer', { friend, answer });
    hideIncomingCallModal();
  } catch (err) {
    alert('Kameraya ve mikrofona erişim reddedildi veya arama kabul edilmedi.');
    console.error(err);
  }
};

// Gelen aramayı reddet
rejectCallBtn.onclick = () => {
  socket.emit('call_end', { friend });
  hideIncomingCallModal();
};

// Socket.io arama eventleri
socket.on('call_offer', async data => {
  if (data.from !== friend) return;

  incomingCallModal.dataset.offer = JSON.stringify(data.offer);

  const isVideoCall = data.call_type === 'video';

  showIncomingCallModal(data.from, isVideoCall);
});

socket.on('call_answer', async data => {
  if (data.from !== friend) return;

  await peerConnection.setRemoteDescription(new RTCSessionDescription(data.answer));
});

socket.on('ice_candidate', async data => {
  if (data.from !== friend) return;

  try {
    if (peerConnection) {
      await peerConnection.addIceCandidate(new RTCIceCandidate(data.candidate));
    } else {
      pendingCandidates.push(data.candidate);
    }
  } catch (e) {
    console.error('ICE candidate eklenirken hata:', e);
  }
});

socket.on('call_end', data => {
  if (data.from === friend) {
    endCall(false);
    alert(`${friend} aramayı sonlandırdı.`);
  }
});

// Call button eventleri
voiceCallBtn.onclick = () => startCall(false);
videoCallBtn.onclick = () => startCall(true);
endCallBtn.onclick = () => endCall();