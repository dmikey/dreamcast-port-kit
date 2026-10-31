/* Three independent GPU stores. Never wait for an in-flight draw: orphan
 * its backing store if its zero-timeout fence is still pending. */
typedef struct {GLuint vao,vbo;GLsync fence;GLsizeiptr capacity;} PortVertexStream;
static PortVertexStream port_streams[3];
static unsigned port_stream_index;
static PortVertexStream *port_active_stream;
static void port_stream_vertices(const PVR2RenderVertex *vertices,int count){
    PortVertexStream *s=&port_streams[port_stream_index++%3];port_active_stream=s;
    if(!s->vao){
        glGenVertexArrays(1,&s->vao);glGenBuffers(1,&s->vbo);
        glBindVertexArray(s->vao);glBindBuffer(GL_ARRAY_BUFFER,s->vbo);
        glVertexAttribPointer(0,3,GL_FLOAT,GL_FALSE,sizeof(PVR2RenderVertex),(void*)0);glEnableVertexAttribArray(0);
        glVertexAttribPointer(1,2,GL_FLOAT,GL_FALSE,sizeof(PVR2RenderVertex),(void*)(3*sizeof(float)));glEnableVertexAttribArray(1);
        glVertexAttribPointer(2,4,GL_FLOAT,GL_FALSE,sizeof(PVR2RenderVertex),(void*)(5*sizeof(float)));glEnableVertexAttribArray(2);
    }else{glBindVertexArray(s->vao);glBindBuffer(GL_ARRAY_BUFFER,s->vbo);}
    int busy=0;
    if(s->fence){GLenum result=glClientWaitSync(s->fence,0,0);busy=result!=GL_ALREADY_SIGNALED && result!=GL_CONDITION_SATISFIED;glDeleteSync(s->fence);s->fence=0;}
    GLsizeiptr bytes=(GLsizeiptr)count*sizeof *vertices;
    if(bytes>s->capacity || busy){
        if(bytes>s->capacity)s->capacity=bytes;
        glBufferData(GL_ARRAY_BUFFER,s->capacity,NULL,GL_STREAM_DRAW);
    }
    glBufferSubData(GL_ARRAY_BUFFER,0,bytes,vertices);
}
static void port_stream_submitted(void){if(port_active_stream)port_active_stream->fence=glFenceSync(GL_SYNC_GPU_COMMANDS_COMPLETE,0);}
static void port_stream_destroy(void){
    for(unsigned i=0;i<3;i++){PortVertexStream *s=&port_streams[i];if(s->fence)glDeleteSync(s->fence);if(s->vbo)glDeleteBuffers(1,&s->vbo);if(s->vao)glDeleteVertexArrays(1,&s->vao);*s=(PortVertexStream){0};}
    port_active_stream=NULL;port_stream_index=0;
}
