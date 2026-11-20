import * as THREE from '/static/vendor/three.module.js';

let disposeCurrent = null;
let disposeSetup = null;

export function mountResearchScene(host) {
  if (disposeCurrent) disposeCurrent();
  if (!host || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const width = host.clientWidth;
  const height = host.clientHeight;
  if (!width || !height) return;
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: 'low-power' });
  } catch {
    return;
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
  renderer.setSize(width, height);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  host.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(42, width / height, .1, 100);
  camera.position.set(0, 0, 8);
  const group = new THREE.Group();
  group.position.set(.55, .15, 0);
  scene.add(group);
  const cool = new THREE.LineBasicMaterial({ color: 0x9dc4c0, transparent: true, opacity: .5 });
  const warm = new THREE.LineBasicMaterial({ color: 0xff8658, transparent: true, opacity: .82 });
  // A sampled surface z = sin(r) / r: a real coordinate plot, animated as a travelling wave.
  const divisions = 34;
  const vertices = [];
  const indices = [];
  for (let row = 0; row <= divisions; row++) {
    const y = -2 + 4 * row / divisions;
    for (let col = 0; col <= divisions; col++) {
      const x = -2 + 4 * col / divisions;
      vertices.push(x, y, 0);
      if (row < divisions && col < divisions) {
        const a = row * (divisions + 1) + col;
        const b = a + divisions + 1;
        indices.push(a, b, a + 1, b, b + 1, a + 1);
      }
    }
  }
  const surfaceGeometry = new THREE.BufferGeometry();
  surfaceGeometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
  surfaceGeometry.setIndex(indices);
  const surface = new THREE.Mesh(surfaceGeometry, new THREE.MeshBasicMaterial({
    color: 0xa9ccc0, wireframe: true, transparent: true, opacity: .45, side: THREE.DoubleSide,
  }));
  surface.position.z = -.05;
  group.add(surface);
  const axes = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(-2.5, 0, 0), new THREE.Vector3(2.5, 0, 0),
    new THREE.Vector3(0, -2.35, 0), new THREE.Vector3(0, 2.35, 0),
    new THREE.Vector3(0, 0, -.8), new THREE.Vector3(0, 0, 1.1),
  ]), cool);
  group.add(axes);
  const xAxis = new THREE.Line(new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(-2.5, 0, .01), new THREE.Vector3(2.5, 0, .01),
  ]), warm);
  group.add(xAxis);
  const curvePoints = [];
  for (let step = 0; step <= 180; step++) {
    const t = step / 180 * Math.PI * 4;
    curvePoints.push(new THREE.Vector3(1.15 * Math.cos(t), 1.15 * Math.sin(t), .48 * Math.sin(2 * t)));
  }
  const helix = new THREE.Line(new THREE.BufferGeometry().setFromPoints(curvePoints), warm);
  helix.material.opacity = .72;
  group.add(helix);
  const nodes = [];
  const positions = [[-1.65,.45,.2],[1.37,1.05,.1],[1.02,-1.3,.4],[-.3,1.55,-.35],[-1.15,-1.04,.1]];
  positions.forEach((position, index) => {
    const point = new THREE.Mesh(new THREE.OctahedronGeometry(index === 1 ? .12 : .075), new THREE.MeshBasicMaterial({ color: index === 1 ? 0xff8c60 : 0xe2e8de }));
    point.position.set(...position);
    group.add(point);
    nodes.push(point);
  });
  const linePoints = positions.map(p => new THREE.Vector3(...p));
  const connections = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints([linePoints[0],linePoints[3],linePoints[3],linePoints[1],linePoints[1],linePoints[2],linePoints[2],linePoints[4]]), cool);
  group.add(connections);
  const axis = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(-2.2,0,0),new THREE.Vector3(2.2,0,0)]), warm);
  axis.material.opacity = .35;
  group.add(axis);

  let running = true;
  let frame = 0;
  const observer = new IntersectionObserver(entries => { running = entries[0].isIntersecting; if (running) animate(); });
  observer.observe(host);
  let scheduled = false;
  function animate() {
    if (!running || scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      if (!running) return;
      frame += .004;
      const position = surfaceGeometry.attributes.position;
      for (let row = 0; row <= divisions; row++) {
        for (let col = 0; col <= divisions; col++) {
          const index = row * (divisions + 1) + col;
          const x = -2 + 4 * col / divisions;
          const y = -2 + 4 * row / divisions;
          const radius = Math.hypot(x, y);
          position.setZ(index, .5 * Math.sin(radius * 3 - frame * 2) * Math.exp(-radius * .38));
        }
      }
      position.needsUpdate = true;
      group.rotation.y = frame;
      group.rotation.x = .63 + Math.sin(frame * .7) * .045;
      renderer.render(scene, camera);
      animate();
    });
  }
  animate();
  const resize = new ResizeObserver(() => {
    const w = host.clientWidth, h = host.clientHeight;
    if (!w || !h) return;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h);
  });
  resize.observe(host);
  disposeCurrent = () => {
    running = false;
    observer.disconnect();
    resize.disconnect();
    surfaceGeometry.dispose();
    surface.material.dispose();
    axes.geometry.dispose();
    connections.geometry.dispose();
    axis.geometry.dispose();
    nodes.forEach(node => { node.geometry.dispose(); node.material.dispose(); });
    cool.dispose();warm.dispose();xAxis.geometry.dispose();helix.geometry.dispose();
    renderer.dispose();
    renderer.domElement.remove();
  };
}

export function mountSetupScene(host) {
  if (disposeSetup) { disposeSetup(); disposeSetup = null; }
  if (!host || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const width=host.clientWidth, height=host.clientHeight;
  if(!width||!height)return;
  let renderer;
  try{renderer=new THREE.WebGLRenderer({alpha:true,antialias:true,powerPreference:'low-power'});}catch{return;}
  renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,1.5));
  renderer.setSize(width,height);
  renderer.outputColorSpace=THREE.SRGBColorSpace;
  host.appendChild(renderer.domElement);
  const scene=new THREE.Scene();
  const camera=new THREE.PerspectiveCamera(38,width/height,.1,100);
  camera.position.set(0,0,7);
  const system=new THREE.Group();
  scene.add(system);
  const coreGeometry=new THREE.IcosahedronGeometry(1.2,2);
  const core=new THREE.LineSegments(
    new THREE.WireframeGeometry(coreGeometry),
    new THREE.LineBasicMaterial({color:0x8ff3c5,transparent:true,opacity:.5}),
  );
  system.add(core);
  const rings=[];
  [[2.05,.025,0x77d9d0],[2.55,.018,0xff8158],[3.0,.012,0x8ff3c5]].forEach(([radius,tube,color],index)=>{
    const ring=new THREE.Mesh(
      new THREE.TorusGeometry(radius,tube,6,120),
      new THREE.MeshBasicMaterial({color,transparent:true,opacity:index===1?.8:.42}),
    );
    ring.rotation.set(index*.58,.35+index*.5,index*.72);
    system.add(ring);rings.push(ring);
  });
  const nodes=[];
  for(let i=0;i<9;i++){
    const angle=i/9*Math.PI*2;
    const node=new THREE.Mesh(
      new THREE.OctahedronGeometry(i%3===0?.105:.065),
      new THREE.MeshBasicMaterial({color:i%3===0?0xff8961:0xd9fff0}),
    );
    node.position.set(Math.cos(angle)*2.55,Math.sin(angle)*1.28,Math.sin(angle*2)*1.25);
    system.add(node);nodes.push(node);
  }
  const path=[];
  for(let i=0;i<=220;i++){
    const t=i/220*Math.PI*4;
    path.push(new THREE.Vector3(2.15*Math.cos(t),1.05*Math.sin(2*t),.72*Math.sin(3*t)));
  }
  const orbit=new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(path),
    new THREE.LineBasicMaterial({color:0x6cb9ab,transparent:true,opacity:.26}),
  );
  system.add(orbit);
  let active=true, frame=0;
  function animate(){
    if(!active)return;
    requestAnimationFrame(animate);
    frame+=.004;
    system.rotation.y=frame;
    system.rotation.x=.12+Math.sin(frame*.7)*.08;
    core.rotation.z=-frame*1.7;
    rings.forEach((ring,index)=>ring.rotation.z+=.0008*(index+1));
    nodes.forEach((node,index)=>node.scale.setScalar(1+.22*Math.sin(frame*5+index)));
    renderer.render(scene,camera);
  }
  animate();
  const resize=new ResizeObserver(()=>{
    const w=host.clientWidth,h=host.clientHeight;if(!w||!h)return;
    camera.aspect=w/h;camera.updateProjectionMatrix();renderer.setSize(w,h);
  });
  resize.observe(host);
  disposeSetup=()=>{
    active=false;resize.disconnect();
    core.geometry.dispose();core.material.dispose();coreGeometry.dispose();
    rings.forEach(item=>{item.geometry.dispose();item.material.dispose();});
    nodes.forEach(item=>{item.geometry.dispose();item.material.dispose();});
    orbit.geometry.dispose();orbit.material.dispose();renderer.dispose();renderer.domElement.remove();
  };
}
