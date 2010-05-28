/* ######################################
 *   conversion of angular coordinates
 *   to reciprocal space
 *   using general algorithms to work 
 *   for different types of geometries
 *   and detectors
 * ######################################*/

#include "rot_matrix.h"
#include "vecmat3.h"
#include <stdio.h>
#include <ctype.h>
#ifdef __OPENMP__
#include <omp.h>
#endif

int determine_axes_directions(fp_rot *fp_circles,char *stringAxis,int n);
int determine_detector_pixel(double *rpixel,char *dir, double dpixel);
int print_matrix(double *m);

/* #######################################
 *  conversion functions
 * #######################################*/

int ang2q_conversion(double *sampleAngles,double *detectorAngles, double *qpos, double *ri, int Ns, int Nd, int Npoints, char *sampleAxis, char *detectorAxis, double lambda) 
   /* conversion of Npoints of goniometer positions to reciprocal space
    * for a setup with point detector
    *
    * Interface:
    *   sampleAngles .. angular positions of the sample goniometer (Npoints,Ns) (in)
    *   detectorAngles. angular positions of the detector goniometer (Npoints,Nd) (in)
    *   qpos .......... momentum transfer (Npoints,3) (out)
    *   ri ............ direction of primary beam (length irrelevant) (angles zero) (in)
    *   Ns ............ number of sample circles (in)
    *   Nd ............ number of detector circles (in)
    *   Npoints ....... number of goniometer positions (in)
    *   sampleAxis .... string with sample axis directions (in)
    *   detectorAxis .. string with detector axis directions (in) 
    *   lambda ........ wavelength of the used x-rays (Angstreom) (in)
    *   */
{
    double mtemp[9],mtemp2[9], ms[9], md[9]; //matrices
    int i,j; // needed indices

    #ifdef __OPENMP__
    //set openmp thread numbers dynamically
    omp_set_dynamic(1);
    #endif
    
    // arrays with function pointers to rotation matrix functions
    fp_rot sampleRotation[Ns];
    fp_rot detectorRotation[Nd];

    //printf("general conversion ang2q\n");    
    // determine axes directions
    if(determine_axes_directions(sampleRotation,sampleAxis,Ns) != 0) {
        printf("sample axes determination failed\n");
        return 1; 
    }
    if(determine_axes_directions(detectorRotation,detectorAxis,Nd) != 0) {
        printf("detector axes determination failed\n");
        return 1; 
    }
    
    // give ri correct length
    normalize(ri);
    vecmul(ri,M_2PI/lambda);

    // calculate rotation matices and perform rotations
    #pragma omp parallel for default(shared) \
            private(i,j,mtemp,mtemp2,ms,md) \
            schedule(static) 
    for(i=0; i<Npoints; ++i) {
        // determine sample rotations
        ident(mtemp);
        for(j=0; j<Ns; ++j) {
            sampleRotation[j](sampleAngles[Ns*i+j],mtemp2);
            matmul(mtemp,mtemp2);
        }
        inversemat(mtemp,ms);

        // determine detector rotations
        ident(md);
        for (j=0; j<Nd; ++j) {
            detectorRotation[j](detectorAngles[Nd*i+j],mtemp);
            matmul(md,mtemp);
        }
        ident(mtemp);
        diffmat(md,mtemp);

        matmul(ms,md);
        // ms contains now the rotation matrix to determine the momentum transfer
        // calculate the momentum transfer
        matvec(ms, ri, &qpos[3*i]); 
    }

    return 0;
}

int ang2q_conversion_linear(double *sampleAngles, double *detectorAngles, double *qpos, double *rcch, int Ns, int Nd, int Npoints, char *sampleAxis, char *detectorAxis,  double cch, double dpixel, int *roi, char *dir, double lambda) 
   /* conversion of Npoints of goniometer positions to reciprocal space
    * for a linear detector with a given pixel size mounted along one of
    * the coordinate axis
    *
    * Interface:
    *   sampleAngles .... angular positions of the goniometer (Npoints,Ns) (in)
    *   detectorAngles .. angular positions of the detector goniometer (Npoints,Nd) (in)
    *   qpos ............ momentum transfer (Npoints*Nch,3) (out)
    *   rcch ............ direction + distance of center channel (angles zero) (in)
    *   Ns .............. number of sample circles (in)
    *   Nd .............. number of detector circles (in)
    *   Npoints ......... number of goniometer positions (in)
    *   sampleAxis ...... string with sample axis directions (in)
    *   detectorAxis .... string with detector axis directions (in) 
    *   cch ............. center channel of the detector (in)
    *   dpixel .......... width of one pixel, same unit as distance rcch (in)
    *   roi ............. region of interest of the detector (in)
    *   dir ............. direction of the detector, e.g.: "x+" (in)
    *   lambda .......... wavelength of the used x-rays in Angstroem (in)
    *   */
{
    double mtemp[9],mtemp2[9], ms[9], md[9]; //matrices
    double rd[3],rpixel[3],rcchp[3]; // detector position
    double r_i[3],rtemp[3]; //center channel direction
    double f = M_2PI/lambda;
    int i,j,k; // loop indices
    int Nch = roi[1]-roi[0]; // number of channels

    #ifdef __OPENMP__
    //set openmp thread numbers dynamically
    omp_set_dynamic(1);
    #endif

    // arrays with function pointers to rotation matrix functions
    fp_rot sampleRotation[Ns];
    fp_rot detectorRotation[Nd];

    //printf("general conversion ang2q (linear detector)\n");    
    // determine axes directions
    if(determine_axes_directions(sampleRotation,sampleAxis,Ns) != 0) {
        printf("sample axes determination failed\n");
        return 1; 
    }
    if(determine_axes_directions(detectorRotation,detectorAxis,Nd) != 0) {
        printf("detector axes determination failed\n");
        return 1; 
    }

    // determine detector pixel vector
    if(determine_detector_pixel(rpixel, dir, dpixel) != 0) {
        printf("detector direction determination failed\n");
        return 1;
    };
    for(int k=0; k<3; ++k)
        rcchp[k] = rpixel[k]*cch;
    veccopy(r_i,rcch);
    normalize(r_i);


    // calculate rotation matices and perform rotations
    #pragma omp parallel for default(shared) \
            private(i,j,k,mtemp,mtemp2,ms,md,rd,rtemp) \
            schedule(static) 
    for(i=0; i<Npoints; ++i) {
        // determine sample rotations
        ident(mtemp);
        for(j=0; j<Ns; ++j) {
            sampleRotation[j](sampleAngles[Ns*i+j],mtemp2);
            matmul(mtemp,mtemp2);
        }
        inversemat(mtemp,ms);

        // determine detector rotations
        ident(md);
        for (j=0; j<Nd; ++j) {
            detectorRotation[j](detectorAngles[Nd*i+j],mtemp);
            matmul(md,mtemp);
        }

        // ms contains now the inverse rotation matrix for the sample circles
        // md contains the detector rotation matrix
        // calculate the momentum transfer for each detector pixel
        for (j=roi[0]; j<roi[1]; ++j) {
            for (k=0; k<3; ++k) 
                rd[k] = j*rpixel[k] - rcchp[k];
            sumvec(rd,rcch);
            normalize(rd);
            // rd contains detector pixel direction, r_i contains primary beam direction
            matvec(md,rd,rtemp);
            diffvec(rtemp,r_i); 
            vecmul(rtemp,f);
            // determine momentum transfer
            matvec(ms, rtemp, &qpos[3*(i*Nch+j-roi[0])]); 
        }
    }

    return 0;
}

int ang2q_conversion_area(double *sampleAngles, double *detectorAngles, double *qpos, double *rcch, int Ns, int Nd, int Npoints, char *sampleAxis, char *detectorAxis, double cch1, double cch2, double dpixel1, double dpixel2, int *roi, char *dir1, char *dir2, double lambda) 
   /* conversion of Npoints of goniometer positions to reciprocal space
    * for a area detector with a given pixel size mounted along one of
    * the coordinate axis
    *
    * Interface:
    *   sampleAngles .... angular positions of the sample goniometer (Npoints,Ns) (in)
    *   detectorAngles .. angular positions of the detector goniometer (Npoints,Nd) (in)
    *   qpos ............ momentum transfer (Npoints*Npix1*Npix2,3) (out)
    *   rcch ............ direction + distance of center pixel (angles zero) (in)
    *   Ns .............. number of sample circles (in)
    *   Nd .............. number of detector circles (in)
    *   Npoints ......... number of goniometer positions (in)
    *   sampleAxis ...... string with sample axis directions (in)
    *   detectorAxis .... string with detector axis directions (in) 
    *   cch1 ............ center channel of the detector (in)
    *   cch2 ............ center channel of the detector (in)
    *   dpixel1 ......... width of one pixel in first direction, same unit as distance rcch (in)
    *   dpixel2 ......... width of one pixel in second direction, same unit as distance rcch (in)
    *   roi ............. region of interest for the area detector [dir1min,dir1max,dir2min,dir2max]
    *   dir1 ............ first direction of the detector, e.g.: "x+" (in)
    *   dir2 ............ second direction of the detector, e.g.: "z+" (in)
    *   lambda .......... wavelength of the used x-rays (in)
    *   */
{
    double mtemp[9],mtemp2[9], ms[9], md[9]; //matrices
    double rd[3],rpixel1[3],rpixel2[3],rcchp[3]; // detector position
    double r_i[3],rtemp[3]; //center channel direction
    double f = M_2PI/lambda;
    int i,j,j1,j2,k; // loop indices
    int idxh1,idxh2; // temporary index helper 
   
    #ifdef __OPENMP__
    //set openmp thread numbers dynamically
    omp_set_dynamic(1);
    #endif
   
    // arrays with function pointers to rotation matrix functions
    fp_rot sampleRotation[Ns];
    fp_rot detectorRotation[Nd];

    //printf("general conversion ang2q (area detector)\n");    
    // determine axes directions
    if(determine_axes_directions(sampleRotation,sampleAxis,Ns) != 0) {
        printf("sample axes determination failed\n");
        return 1; 
    }
    if(determine_axes_directions(detectorRotation,detectorAxis,Nd) != 0) {
        printf("detector axes determination failed\n");
        return 1; 
    }

    // determine detector pixel vector
    if(determine_detector_pixel(rpixel1, dir1, dpixel1) != 0) {
        printf("detector direction determination failed\n");
        return 1;
    };
    if(determine_detector_pixel(rpixel2, dir2, dpixel2) != 0) {
        printf("detector direction determination failed\n");
        return 1;
    };
    for(int k=0; k<3; ++k)
        rcchp[k] = rpixel1[k]*cch1 + rpixel2[k]*cch2;
    veccopy(r_i,rcch);
    normalize(r_i);

    // calculate some index shortcuts  
    idxh1 = (roi[1]-roi[0])*(roi[3]-roi[2]);
    idxh2 = roi[1]-roi[0];

    // calculate rotation matices and perform rotations
    #pragma omp parallel for default(shared) \
            private(i,j,j1,j2,k,mtemp,mtemp2,ms,md,rd,rtemp) \
            schedule(static) 
    for(i=0; i<Npoints; ++i) {
        // determine sample rotations
        ident(mtemp);
        for(j=0; j<Ns; ++j) {
            sampleRotation[j](sampleAngles[Ns*i+j],mtemp2);
            matmul(mtemp,mtemp2);
        }
        inversemat(mtemp,ms);

        // determine detector rotations
        ident(md);
        for (j=0; j<Nd; ++j) {
            detectorRotation[j](detectorAngles[Nd*i+j],mtemp);
            matmul(md,mtemp);
        }

        // ms contains now the inverse rotation matrix for the sample circles
        // md contains the detector rotation matrix
        // calculate the momentum transfer for each detector pixel
        for (j1=roi[0]; j1<roi[1]; ++j1) {
            for (j2=roi[2]; j2<roi[3]; ++j2) {
                for (k=0; k<3; ++k) 
                    rd[k] = j1*rpixel1[k] + j2*rpixel2[k] - rcchp[k];
                sumvec(rd,rcch);
                normalize(rd);
                // rd contains detector pixel direction, r_i contains primary beam direction
                matvec(md,rd,rtemp);
                diffvec(rtemp,r_i); 
                vecmul(rtemp,f);
                // determine momentum transfer
                matvec(ms, rtemp, &qpos[3*(i*idxh1+idxh2*(j2-roi[2])+(j1-roi[0]))]);
            }
        }
    }

    return 0;
}

/* #######################################
 *  conversion functions
 * #######################################*/

int print_matrix(double *m) {
    for(int i=0;i<9;i+=3) {
        printf("%8.3f %8.3f %8.3f\n",m[i],m[i+1],m[i+2]);
    }
    printf("\n");
    return 0;
}

int determine_detector_pixel(double *rpixel,char *dir, double dpixel) {
    /* determine the direction of linear direction or one of the directions
     * of an area detector. 
     * the function returns the vector containing the distance from one to
     * the next pixel
     * */

    for(int i=0; i<3; ++i)
        rpixel[i] = 0.;

    switch(tolower(dir[0])) {
        case 'x':
            switch(dir[1]) {
                case '+':
                    rpixel[0] = dpixel;
                break;
                case '-':
                    rpixel[0] = -dpixel;
                break;
                default:
                    printf("detector determination: no valid direction sign given\n");
                    return 1;
            }
        break;
        case 'y':
            switch(dir[1]) {
                case '+':
                    rpixel[1] = dpixel;
                break;
                case '-':
                    rpixel[1] = -dpixel;
                break;
                default:
                    printf("detector determination: no valid direction sign given\n");
                    return 1;
            }
        break;
        case 'z':
            switch(dir[1]) {
                case '+':
                    rpixel[2] = dpixel;
                break;
                case '-':
                    rpixel[2] = -dpixel;
                break;
                default:
                    printf("detector determination: no valid direction sign given\n");
                    return 1;
            }
        break;
        default:
            printf("detector determination: no valid detector direction given\n");
            return 2;
    }
    return 0;
}

int determine_axes_directions(fp_rot *fp_circles,char *stringAxis,int n) {
    /* feed the function pointer array with the correct
     * rotation matrix generating functions
     * */
    
    for(int i=0; i<n; ++i) {
        switch(tolower(stringAxis[2*i])) {
            case 'x':
                switch(stringAxis[2*i+1]) {
                    case '+':
                        fp_circles[i] = &rotation_xp;
                    break;
                    case '-':
                        fp_circles[i] = &rotation_xm;
                    break;
                    default:
                        printf("axis determination: no valid rotation sense found\n");
                        return 1;
                }
            break;
            case 'y':
                switch(stringAxis[2*i+1]) {
                    case '+':
                        fp_circles[i] = &rotation_yp;
                    break;
                    case '-':
                        fp_circles[i] = &rotation_ym;
                    break;
                    default:
                        printf("axis determination: no valid rotation sense found\n");
                        return 1;
                }
            break;
            case 'z':
                switch(stringAxis[2*i+1]) {
                    case '+':
                        fp_circles[i] = &rotation_zp;
                    break;
                    case '-':
                        fp_circles[i] = &rotation_zm;
                    break;
                    default:
                        printf("axis determination: no valid rotation sense found\n");
                        return 1;
                }
            break;
            default:
                printf("axis determination: no valid axis direction found!\n");
                return 2;
        }
    }

    return 0;
}
